import collections
import importlib
import logging
import os
import time

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

from . import reactor, gcode, pins, heater, mcu, toolhead, msgproto
from .strings import message_ready, message_startup, message_restart, message_protocol_error, \
    message_mcu_connect_error, message_shutdown
from .config import ConfigWrapper, ConfigLogger


class Printer:
    config_error = ConfigParser.Error
    def __init__(self, input_fd, bglogger, start_args):
        self.bglogger = bglogger
        self.start_args = start_args
        self.reactor = reactor.Reactor()
        gc = gcode.GCodeParser(self, input_fd)
        self.objects = collections.OrderedDict({'gcode': gc})
        self.reactor.register_callback(self._connect)
        self.state_message = message_startup
        self.is_shutdown = False
        self.run_result = None
        self.state_cb = [gc.printer_state]
    def get_start_args(self):
        return self.start_args
    def get_reactor(self):
        return self.reactor
    def get_state_message(self):
        return self.state_message
    def _set_state(self, msg):
        self.state_message = msg
        if (msg != message_ready
            and self.start_args.get('debuginput') is not None):
            self.request_exit('error_exit')
    def add_object(self, name, obj):
        if obj in self.objects:
            raise self.config_error(
                "Printer object '%s' already created" % (name,))
        self.objects[name] = obj
    def lookup_object(self, name, default=ConfigWrapper.sentinel):
        if name in self.objects:
            return self.objects[name]
        if default is ConfigWrapper.sentinel:
            raise self.config_error("Unknown config object '%s'" % (name,))
        return default
    def lookup_objects(self, module=None):
        if module is None:
            return list(self.objects.items())
        prefix = module + ' '
        objs = [(n, self.objects[n])
                for n in self.objects if n.startswith(prefix)]
        if module in self.objects:
            return [(module, self.objects[module])] + objs
        return objs
    def set_rollover_info(self, name, info, log=True):
        if log:
            logging.info(info)
        if self.bglogger is not None:
            self.bglogger.set_rollover_info(name, info)
    def try_load_module(self, config, section):
        if section in self.objects:
            return self.objects[section]
        module_parts = section.split()
        module_name = module_parts[0]
        py_name = os.path.join(os.path.dirname(__file__),
                               'extras', module_name + '.py')
        py_dirname = os.path.join(os.path.dirname(__file__),
                                  'extras', module_name, '__init__.py')
        if not os.path.exists(py_name) and not os.path.exists(py_dirname):
            return None
        mod = importlib.import_module('.extras.' + module_name, package="klippy")
        init_func = 'load_config'
        if len(module_parts) > 1:
            init_func = 'load_config_prefix'
        init_func = getattr(mod, init_func, None)
        if init_func is not None:
            self.objects[section] = init_func(config.getsection(section))
            return self.objects[section]
    def _read_config(self):
        fileconfig = ConfigParser.RawConfigParser()
        config_file = self.start_args['config_file']
        res = fileconfig.read(config_file)
        if not res:
            raise self.config_error("Unable to open config file %s" % (
                config_file,))
        if self.bglogger is not None:
            ConfigLogger(fileconfig, self.bglogger)
        # Create printer components
        access_tracking = {}
        config = ConfigWrapper(self, fileconfig, access_tracking, 'printer')
        for m in [pins, heater, mcu]:
            m.add_printer_objects(config)
        for section in fileconfig.sections():
            self.try_load_module(config, section)
        for m in [toolhead]:
            m.add_printer_objects(config)
        # Validate that there are no undefined parameters in the config file
        valid_sections = { s: 1 for s, o in access_tracking }
        for section_name in fileconfig.sections():
            section = section_name.lower()
            if section not in valid_sections and section not in self.objects:
                raise self.config_error(
                    "Section '%s' is not a valid config section" % (section,))
            for option in fileconfig.options(section_name):
                option = option.lower()
                if (section, option) not in access_tracking:
                    raise self.config_error(
                        "Option '%s' is not valid in section '%s'" % (
                            option, section))
        # Determine which printer objects have state callbacks
        self.state_cb = [o.printer_state for o in self.objects.values()
                         if hasattr(o, 'printer_state')]
    def _connect(self, eventtime):
        try:
            self._read_config()
            for cb in self.state_cb:
                if self.state_message is not message_startup:
                    return self.reactor.NEVER
                cb('connect')
            self._set_state(message_ready)
            for cb in self.state_cb:
                if self.state_message is not message_ready:
                    return self.reactor.NEVER
                cb('ready')
        except (self.config_error, pins.error) as e:
            logging.exception("Config error")
            self._set_state("%s%s" % (str(e), message_restart))
        except msgproto.error as e:
            logging.exception("Protocol error")
            self._set_state("%s%s" % (str(e), message_protocol_error))
        except mcu.error as e:
            logging.exception("MCU error during connect")
            self._set_state("%s%s" % (str(e), message_mcu_connect_error))
        except:
            logging.exception("Unhandled exception during connect")
            self._set_state("Internal error during connect.%s" % (
                message_restart,))
        return self.reactor.NEVER
    def run(self):
        systime = time.time()
        monotime = self.reactor.monotonic()
        logging.info("Start printer at %s (%.1f %.1f)",
                     time.asctime(time.localtime(systime)), systime, monotime)
        # Enter main reactor loop
        try:
            self.reactor.run()
        except:
            logging.exception("Unhandled exception during run")
            return "error_exit"
        # Check restart flags
        run_result = self.run_result
        try:
            if run_result == 'firmware_restart':
                for n, m in self.lookup_objects(module='mcu'):
                    m.microcontroller_restart()
            for cb in self.state_cb:
                cb('disconnect')
        except:
            logging.exception("Unhandled exception during post run")
        return run_result
    def invoke_shutdown(self, msg):
        if self.is_shutdown:
            return
        self.is_shutdown = True
        self._set_state("%s%s" % (msg, message_shutdown))
        for cb in self.state_cb:
            cb('shutdown')
    def invoke_async_shutdown(self, msg):
        self.reactor.register_async_callback(
            (lambda e: self.invoke_shutdown(msg)))
    def request_exit(self, result):
        self.run_result = result
        self.reactor.end()
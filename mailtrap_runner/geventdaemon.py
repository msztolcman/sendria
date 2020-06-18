import daemon
import signal


# Moved gevent imports into functions.
# See http://stackoverflow.com/q/11587164/298479
# TLDR: Importing gevent before forking is a bad idea


class GeventDaemonContext(daemon.DaemonContext):
    """ DaemonContext for gevent.

    Receive same options as a DaemonContext (python-daemon), Except:

    `monkey`: None by default, does nothing. Else it can be a dict or
    something that evaluate to True.
    If it is True, it patches all. (gevent.monkey.patch_all()).
    If it is a dict, it pass the dict as keywords arguments to patch_all().

    `signal_map`: receives a dict of signals, but handler is either a
    callable, a list of arguments [callable, arg1, arg2] or
    a string.
    callable without arguments will receive (signal, None) as arguments,
    meaning the `frame` parameter is always None.

    If the daemon context forks. It calls gevent.reinit().
    """

    def __init__(self, monkey_greenlet_report=True, monkey=True, gevent_hub=None, signal_map=None, **daemon_options):
        self.gevent_signal_map = signal_map
        self.monkey = monkey
        self.monkey_greenlet_report = monkey_greenlet_report
        self.gevent_hub = gevent_hub
        super(GeventDaemonContext, self).__init__(signal_map={}, **daemon_options)
        # python-daemon>=2.1 has initgroups=True by default but it requires root privs
        # older versions don't have the kwarg so we set it manually instead of using
        # the constructor argument
        self.initgroups = False

    def open(self):
        super(GeventDaemonContext, self).open()
        # always reinit even when not forked when registering signals
        self._apply_monkey_patch()
        import gevent
        if self.gevent_hub is not None:
            # gevent 1.0 only
            gevent.get_hub(self.gevent_hub)
        gevent.reinit()
        self._setup_gevent_signals()

    def _apply_monkey_patch(self):
        import gevent
        import gevent.monkey
        if isinstance(self.monkey, dict):
            gevent.monkey.patch_all(**self.monkey)
        elif self.monkey:
            gevent.monkey.patch_all()

        if self.monkey_greenlet_report:
            import logging
            original_report = gevent.hub.Hub.print_exception

            def print_exception(self, context, type, value, tb):
                try:
                    logging.error("Error in greenlet: %s" % str(context), exc_info=(type, value, tb))
                finally:
                    return original_report(self, context, type, value, tb)

            gevent.hub.Hub.print_exception = print_exception

    def _setup_gevent_signals(self):
        import gevent
        if self.gevent_signal_map is None:
            gevent.signal_handler(signal.SIGTERM, self.terminate, signal.SIGTERM, None)
            return

        for sig, target in self.gevent_signal_map.items():
            if target is None:
                raise ValueError('invalid handler argument for signal %s', str(sig))
            tocall = target
            args = [sig, None]
            if isinstance(target, list):
                if not target:
                    raise ValueError('handler list is empty for signal %s', str(sig))
                tocall = target[0]
                args = target[1:]
            elif isinstance(target, str):
                assert not target.startswith('_')
                tocall = getattr(self, target)

            gevent.signal_handler(sig, tocall, *args)

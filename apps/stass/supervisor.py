"""Own a user-scoped service mutex and receive graceful Windows shutdown events."""
import argparse
import threading

from runtime_state import RuntimeState, installation_lock
from runtime_control import event_api, event_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    runtime = RuntimeState(args.root)
    state = runtime.read()
    # Separate lifetime lock: the management lock must remain available for stop.
    with installation_lock(runtime.root / 'config' / 'service-owner', 0):
        import uvicorn
        kernel = event_api()
        handle = kernel.CreateEventW(None, True, False, event_name(state))
        if not handle:
            raise RuntimeError('Cannot create service shutdown event')
        server = uvicorn.Server(uvicorn.Config('service:app', host='127.0.0.1', port=state['port']))
        finished = threading.Event()
        def wait():
            while not finished.is_set():
                if kernel.WaitForSingleObject(handle, 200) == 0:
                    server.should_exit = True
                    return
        watcher = threading.Thread(target=wait, daemon=True)
        watcher.start()
        try:
            server.run()
        finally:
            finished.set()
            watcher.join()
            kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()

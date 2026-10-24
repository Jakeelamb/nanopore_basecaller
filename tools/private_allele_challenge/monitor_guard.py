import json
import os


def fail_closed(failures, event, retain, stop):
    failures.append(event)
    try:
        retain(event)
    except BaseException as error:
        event['retention_error'] = f'{type(error).__name__}: {error}'
        try:
            os.write(2, (json.dumps(event) + '\n').encode())
        except BaseException:
            pass
    finally:
        stop()


def guarded_monitor(done, sample, reject, interval=0.5):
    try:
        while not done.wait(interval):
            sample()
    except BaseException as error:
        reject(dict(reason='monitor_sampling_exception', error_type=type(error).__name__, error=str(error)))

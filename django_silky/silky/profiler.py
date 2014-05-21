from copy import copy
import inspect
import time
import traceback

from django.utils import timezone

from silky import models
from silky.local import DataCollector
from silky.models import Profile


class silky_profile(object):
    def __init__(self, name=None):
        self.name = name
        self.profile = None
        self._queries_before = None
        self._queries_after = None

    def _start_queries(self):
        self._queries_before = copy(DataCollector().request_queries)

    def __enter__(self):
        self._start_queries()
        if not self.name:
            raise ValueError('silky_profile used as a context manager must have a name')
        frame = inspect.currentframe()
        frames = inspect.getouterframes(frame)
        outer_frame = frames[1]
        path = outer_frame[1]
        line_num = outer_frame[2]
        self.profile = Profile(name=self.name,
                               file_path=path,
                               line_num=line_num)

    def _finalise_queries(self):
        self._queries_after = copy(DataCollector().request_queries)
        assert self.profile, 'no profile was created'
        DataCollector().register_queries_for_profile(self.profile, self.distinct_queries())

    def __exit__(self, exc_type, exc_val, exc_tb):
        exception_raised = exc_type is not None
        self.profile.exception_raised = exception_raised
        self.profile.end_time = timezone.now()
        self._finalise_queries()

    def __call__(self, target):
        def wrapped_target(*args, **kwargs):
            if hasattr(target, 'func_code'):
                line_num = target.func_code.co_firstlineno
                file_path = target.func_code.co_filename
                func_name = target.__name__
                if not self.name:
                    self.name = func_name
                self.profile = Profile(func_name=func_name,
                                       name=self.name,
                                       file_path=file_path,
                                       line_num=line_num)
                self._start_queries()
                try:
                    result = target(*args, **kwargs)
                except Exception:
                    self.profile.exception_raised = True
                    raise
                finally:
                    self._finalise_queries()
                    self.profile.end_time = timezone.now()
                return result
            else:
                raise NotImplementedError('Profile not implemented to decorate type %s', target.__class__.__name__)

        return wrapped_target

    def distinct_queries(self):
        queries = [x for x in self._queries_after if not x in self._queries_before]
        return queries


@silky_profile()
def blah():
    time.sleep(1)


if __name__ == '__main__':
    blah()
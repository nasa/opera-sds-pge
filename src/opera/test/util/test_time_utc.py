"""Regression tests for UTC time tags on non-UTC hosts."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

import pytest

from opera.util import logger, time as time_util


@pytest.mark.skipif(not hasattr(time, 'tzset'), reason='Requires POSIX TZ support')
@pytest.mark.parametrize('zone', [
    'UTC0', 'EST5', 'JST-9', 'NPT-5:45', 'NST3:30', 'EST5EDT,M3.2.0/2,M11.1.0/2',
])
def test_current_time_and_log_entries_use_utc_in_each_host_zone(zone):
    """Check actual clock readings without changing the parent process timezone."""
    script = """
import json
import time
from datetime import datetime, timezone
from io import StringIO
from opera.util import logger, time as time_util

time.tzset()
before = datetime.now(timezone.utc).isoformat()
value = time_util.get_current_iso_time()
stream = StringIO()
logger.write(stream, 'Info', 'workflow', 'module', 1, 'test', 'message')
pge_logger = logger.PgeLogger(log_filename='unused-test.log')
pge_logger.info('module', 1, 'message')
after = datetime.now(timezone.utc).isoformat()
print(json.dumps([before, after, value, stream.getvalue(), pge_logger.log_stream.getvalue()]))
"""
    result = subprocess.run(
        [sys.executable, '-c', script], env=dict(os.environ, TZ=zone),
        check=True, capture_output=True, text=True, timeout=30,
    )
    before, after, *entries = json.loads(result.stdout)
    for entry in entries:
        tag = entry.split(', ', 1)[0]
        assert len(tag) == 27
        assert tag.endswith('Z')
        parsed = datetime.fromisoformat(tag.replace('Z', '+00:00'))
        assert datetime.fromisoformat(before) <= parsed <= datetime.fromisoformat(after)


@pytest.mark.parametrize('instant, local_minutes', [
    (datetime(2026, 1, 1, 0, 0, 0, 1, tzinfo=timezone.utc), -480),
    (datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc), 840),
    (datetime(2024, 2, 29, 0, 1, 2, 345678, tzinfo=timezone.utc), -210),
    (datetime(2026, 6, 1, 23, 59, 59, 0, tzinfo=timezone.utc), 345),
    (datetime(2026, 9, 26, 12, 13, 14, 123456, tzinfo=timezone.utc), 540),
    (datetime(2026, 9, 26, 12, 13, 14, 0, tzinfo=timezone.utc), 0),
])
def test_utc_calendar_boundaries_and_microseconds(instant, local_minutes):
    """Keep exact UTC dates and fractional seconds rather than local wall time."""
    class FrozenDateTime(datetime):
        """Return one instant with the same timezone semantics as datetime.now."""

        @classmethod
        def now(cls, tz=None):
            """Return a timezone-aware value only when a timezone is requested."""
            if tz is not None:
                return instant.astimezone(tz)
            local_zone = timezone(timedelta(minutes=local_minutes))
            return instant.astimezone(local_zone).replace(tzinfo=None)

    expected = instant.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    with patch.object(time_util, 'datetime', FrozenDateTime):
        assert time_util.get_current_iso_time() == expected
        stream = StringIO()
        logger.write(stream, 'Info', 'workflow', 'module', 1, 'test', 'message')
        assert stream.getvalue() == f'{expected}, Info, workflow, module, 1, test, "message"\n'


def test_explicit_log_time_tag_is_unchanged():
    """A caller-supplied time tag must not consult or be replaced by the clock."""
    stream = StringIO()
    with patch.object(time_util, 'get_current_iso_time', side_effect=AssertionError):
        logger.write(stream, 'Info', 'workflow', 'module', 1, 'test', 'message',
                     time_tag='2024-02-29T12:00:00.123456Z')
    assert stream.getvalue().startswith('2024-02-29T12:00:00.123456Z, Info, ')

import time
import threading
import os


class SnowflakeGenerator:
    """
    Generates unique 64-bit IDs with no coordination needed between
    instances, as long as each instance has a distinct machine_id.

    Bit layout (63 bits used, fits safely in a signed BIGINT):
      41 bits -- milliseconds since EPOCH (~69 years of range)
      10 bits -- machine_id (0-1023, supports up to 1024 concurrent instances)
      12 bits -- per-millisecond sequence (0-4095 IDs/ms/machine)
    """

    EPOCH = 1704067200000  # 2024-01-01T00:00:00Z in milliseconds
    MACHINE_ID_BITS = 10
    SEQUENCE_BITS = 12
    MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1

    def __init__(self, machine_id: int = 0):
        if machine_id < 0 or machine_id > self.MAX_MACHINE_ID:
            raise ValueError(f"machine_id must be between 0 and {self.MAX_MACHINE_ID}")
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1
        # A lock is needed even though Python has a GIL: multiple requests
        # handled by FastAPI's threadpool can call next_id() concurrently,
        # and the read-modify-write on self.sequence must be atomic.
        self._lock = threading.Lock()

    @staticmethod
    def _current_millis() -> int:
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_timestamp: int) -> int:
        timestamp = self._current_millis()
        while timestamp <= last_timestamp:
            timestamp = self._current_millis()
        return timestamp

    def next_id(self) -> int:
        with self._lock:
            timestamp = self._current_millis()

            if timestamp < self.last_timestamp:
                # System clock moved backwards (NTP adjustment, etc).
                # Wait it out rather than risk generating a duplicate or
                # decreasing ID -- correctness over speed in this rare case.
                timestamp = self._wait_next_millis(self.last_timestamp)

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    # Exhausted this millisecond's 4096-ID budget on this
                    # machine -- roll forward to the next millisecond.
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            return (
                ((timestamp - self.EPOCH) << (self.MACHINE_ID_BITS + self.SEQUENCE_BITS))
                | (self.machine_id << self.SEQUENCE_BITS)
                | self.sequence
            )


# MACHINE_ID should differ per deployed instance if you ever run more than
# one (e.g. instance 0 and instance 1 in Render, or M15's multi-instance
# demo). Defaults to 0 for a single-instance setup.
_MACHINE_ID = int(os.getenv("MACHINE_ID", "0"))
_generator = SnowflakeGenerator(machine_id=_MACHINE_ID)


def generate_id() -> int:
    return _generator.next_id()
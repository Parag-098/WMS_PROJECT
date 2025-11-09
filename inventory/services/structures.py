"""
Manual stack and queue implementations for allocation algorithms.
Avoids using Python's built-in queue/deque and pop semantics for clarity in coursework.
"""
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')


class ManualQueue(Generic[T]):
    """A simple circular-buffer FIFO queue with dynamic growth.

    Operations: enqueue, dequeue, peek, is_empty, size.
    Time: Amortized O(1).
    """
    __slots__ = ("_data", "_head", "_tail", "_size")

    def __init__(self, capacity: int = 16) -> None:
        if capacity <= 0:
            capacity = 16
        self._data: List[Optional[T]] = [None] * capacity
        self._head: int = 0
        self._tail: int = 0
        self._size: int = 0

    def _grow(self) -> None:
        old = self._data
        new_cap = max(2 * len(old), 16)
        self._data = [None] * new_cap
        # Copy in FIFO order
        idx = self._head
        for i in range(self._size):
            self._data[i] = old[idx]
            idx = (idx + 1) % len(old)
        self._head = 0
        self._tail = self._size

    def enqueue(self, value: T) -> None:
        if self._size == len(self._data):
            self._grow()
        self._data[self._tail] = value
        self._tail = (self._tail + 1) % len(self._data)
        self._size += 1

    def dequeue(self) -> T:
        if self._size == 0:
            raise IndexError("dequeue from empty queue")
        value = self._data[self._head]
        self._data[self._head] = None
        self._head = (self._head + 1) % len(self._data)
        self._size -= 1
        return value  # type: ignore[return-value]

    def peek(self) -> T:
        if self._size == 0:
            raise IndexError("peek from empty queue")
        return self._data[self._head]  # type: ignore[return-value]

    def is_empty(self) -> bool:
        return self._size == 0

    def size(self) -> int:
        return self._size


class ManualStack(Generic[T]):
    """A dynamic array-backed LIFO stack.

    Operations: push, pop, peek, is_empty, size.
    Time: Amortized O(1).
    """
    __slots__ = ("_data", "_top")

    def __init__(self, capacity: int = 16) -> None:
        if capacity <= 0:
            capacity = 16
        self._data: List[Optional[T]] = [None] * capacity
        self._top: int = 0  # points to next free slot

    def _grow(self) -> None:
        old = self._data
        new_cap = max(2 * len(old), 16)
        self._data = old + [None] * (new_cap - len(old))

    def push(self, value: T) -> None:
        if self._top == len(self._data):
            self._grow()
        self._data[self._top] = value
        self._top += 1

    def pop(self) -> T:
        if self._top == 0:
            raise IndexError("pop from empty stack")
        self._top -= 1
        value = self._data[self._top]
        self._data[self._top] = None
        return value  # type: ignore[return-value]

    def peek(self) -> T:
        if self._top == 0:
            raise IndexError("peek from empty stack")
        return self._data[self._top - 1]  # type: ignore[return-value]

    def is_empty(self) -> bool:
        return self._top == 0

    def size(self) -> int:
        return self._top

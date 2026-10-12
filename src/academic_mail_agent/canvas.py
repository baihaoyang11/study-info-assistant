from typing import Protocol

from pydantic import BaseModel, ConfigDict


class CanvasCourse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    course_code: str
    name: str
    time_zone: str


class CanvasConnector(Protocol):
    """Contract only. Real Canvas access requires future school authorization."""

    def list_courses(self) -> list[CanvasCourse]: ...


class MockCanvasConnector:
    def list_courses(self) -> list[CanvasCourse]:
        return [CanvasCourse(id='mock-1', course_code='DEMO101', name='模拟课程', time_zone='Asia/Shanghai')]

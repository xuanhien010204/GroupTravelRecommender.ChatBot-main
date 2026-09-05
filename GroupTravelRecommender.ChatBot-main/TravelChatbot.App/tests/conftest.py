import socket
import pytest
from config import Settings
from services.backend import create_backend
from agents.controller_agent import ControllerAgent


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("External network is forbidden in offline tests")
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def backend():
    return create_backend(Settings(demo_mode=True))


@pytest.fixture
def agent(backend):
    return ControllerAgent(backend)

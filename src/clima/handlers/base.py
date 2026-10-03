from abc import ABC, abstractmethod

from clima.controllers.users import AuthController
from clima.errors import AuthError
from clima.models.value_objects import Request, Response


class Handler(ABC):
    def __init__(self, authController: AuthController):
        self.authController = authController

    @abstractmethod
    def handle(self, request: Request) -> Response:
        raise NotImplementedError

    def authenticate(self, request: Request) -> int:
        if not request.token:
            raise AuthError("Требуется авторизация")
        session = self.authController.validateSession(request.token)
        request.userId = session.userId
        return session.userId

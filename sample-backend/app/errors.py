from flask import g, jsonify
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException


def register_error_handlers(app) -> None:
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return _response("csrf_failed", error.description, 400)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return _response("http_error", error.description, error.code or 500)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled request error", exc_info=error)
        return _response("internal_error", "Ocurrio un error interno.", 500)


def _response(error: str, message: str, status: int):
    return jsonify(
        error=error,
        message=message,
        request_id=getattr(g, "request_id", None),
    ), status

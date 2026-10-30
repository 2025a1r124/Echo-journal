"""Echo Journal: a private journaling website.

`create_app()` builds the website: it reads the settings, connects the
database, switches on the security features and plugs in the pages.
"""
import logging

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from . import account, auth, db, filters, journal, pages, security
from .config import load_config

ERROR_TEXT = {
    400: ("That didn't work", "The request couldn't be understood. Go back and try again."),
    403: ("Not allowed", "You don't have permission to do that."),
    404: ("Page not found", "That page doesn't exist, or it isn't yours to see."),
    405: ("Not available", "That action isn't available here."),
    413: ("Too much text", "That was too large to send at once. Try a shorter entry."),
    500: ("Something went wrong", "Please try again in a moment."),
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(load_config(test_config))
    # Privacy rule for the whole code base: never log what someone wrote in their journal.
    app.logger.setLevel(logging.INFO)

    if app.config["TRUST_PROXY_HEADERS"]:
        # Only switch this on behind a hosting service's proxy (see README, deployment).
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    security.init_app(app)
    filters.init_app(app)
    for module in (pages, auth, journal, account):
        app.register_blueprint(module.bp)

    @app.errorhandler(security.CSRFError)
    def csrf_failed(error):
        return (
            render_template("errors/error.html", code=400, heading="This form expired", message=error.description),
            400,
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        code = error.code or 500
        heading, message = ERROR_TEXT.get(code, ERROR_TEXT[500])
        return render_template("errors/error.html", code=code, heading=heading, message=message), code

    return app

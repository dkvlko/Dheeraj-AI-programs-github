from flask import Blueprint


test_bp = Blueprint(
    "test_bp",
    __name__,
    template_folder="templates",
    static_folder="static"
)

test_bp.app_url = "/testbp"


@test_bp.route("/")
def index():

    return "Test Blueprint"

from . import routes

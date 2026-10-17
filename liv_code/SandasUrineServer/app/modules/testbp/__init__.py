from flask import Blueprint


test_bp = Blueprint(
    "testbp",
    __name__,
    template_folder="templates",
    static_folder="static"
)

test_bp.app_url = "/mouse_test"


from . import routes

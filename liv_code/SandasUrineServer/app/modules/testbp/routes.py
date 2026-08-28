from flask import render_template

from . import test_bp


@test_bp.route("/test")
def testbp():
    return render_template("test.html")

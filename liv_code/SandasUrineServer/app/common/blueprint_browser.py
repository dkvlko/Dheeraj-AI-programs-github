from flask import Blueprint, render_template, current_app


blueprint_browser = Blueprint(
    "blueprint_browser",
    __name__,
    template_folder="templates"
)


@blueprint_browser.route("/")
def apps():

    applications = []

    for name, blueprint in current_app.blueprints.items():

        # Do not display this utility Blueprint.
        if name == "blueprint_browser":
            continue

        # Only display application Blueprints that
        # explicitly define an app_url.
        app_url = getattr(
            blueprint,
            "app_url",
            None
        )

        if not app_url:
            continue

        applications.append({
            "name": name,
            "url": app_url
        })

    applications.sort(
        key=lambda item: item["name"].lower()
    )

    return render_template(
        "apps.html",
        applications=applications
    )

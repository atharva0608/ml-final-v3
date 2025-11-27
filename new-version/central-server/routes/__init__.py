"""Routes package - contains all API endpoint modules."""

def register_routes(app):
    """Register all route blueprints with the Flask app."""
    from .health import health_bp
    from .admin import admin_bp
    from .clients import clients_bp
    from .agents import agents_bp
    from .instances import instances_bp
    from .replicas import replicas_bp
    from .emergency import emergency_bp
    from .decisions import decisions_bp
    from .commands import commands_bp
    from .reporting import reporting_bp
    from .analytics import analytics_bp
    from .notifications import notifications_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(instances_bp)
    app.register_blueprint(replicas_bp)
    app.register_blueprint(emergency_bp)
    app.register_blueprint(decisions_bp)
    app.register_blueprint(commands_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(notifications_bp)

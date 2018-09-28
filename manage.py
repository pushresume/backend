import click


@click.group()
def cli():
    pass


@cli.command()
@click.option('-h', '--host', default='127.0.0.1', help='listen address')
@click.option('-p', '--port', type=int, default=8000, help='listen port')
def run(host, port):
    """Run development server"""
    from logging import basicConfig
    from app import create_app
    basicConfig(level='DEBUG')
    create_app().run(host=host, port=port)


@cli.command()
def create():
    """Create database tables"""
    from app import create_app, db
    app = create_app()
    with app.app_context():
        db.create_all()


@cli.command()
def drop():
    """Purge database schema - WARNING!"""
    from app import create_app, db
    app = create_app()
    with app.app_context():
        db.drop_all()


@cli.command()
@click.option('-o', '--output', default='html', help='Output dir for docs')
def doc(output):
    """Build documentation with Sphinx"""
    from sphinx.cmd import build
    build.main(['docs', output])


@cli.command()
@click.option('-d', '--dir', default='tests', help='Directory with tests')
def test(dir):
    """Discover and run unit tests"""
    import logging
    from unittest import TestLoader, TextTestRunner
    logging.disable(logging.CRITICAL)
    testsuite = TestLoader().discover(f'./{dir}')
    TextTestRunner(verbosity=2, buffer=True).run(testsuite)


if __name__ == '__main__':
    import sys
    if sys.version_info < (3, 6, 0):
        sys.exit('Python >= 3.6 required')
    cli()

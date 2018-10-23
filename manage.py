import click
from flask.cli import FlaskGroup

from app import create_app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    pass


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

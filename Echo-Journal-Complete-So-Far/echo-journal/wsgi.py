"""Start the site with:  python -m flask --app wsgi run --debug"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()

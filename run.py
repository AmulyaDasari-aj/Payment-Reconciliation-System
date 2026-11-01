
from app import create_app
from database.db import initialize_database

# Initialize the database
initialize_database()

# Create Flask application
app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

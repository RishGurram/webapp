# Webapp

This is a Fast API for managing user data. It includes APIs for registration, login, and user details retrieval and update.


### Requirements
- Python 3.x
- Fast API

### Installation
1. Clone the repository to your local machine and cd into webapp.
2. Create a virtual environment in the project directory.
3. Activate the virtual environment.
4. Install the required packages using the following command:
```bash
pip install -r requirements.txt
```
5. Export the database configurations to the environment. 
```bash
export DATABASE_URL=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```
> **_NOTE:_**  replace the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB with your database configurations.


### Run FastAPI server
- Run server

     $ uvicorn main:app --reload

### Running tests with pytest

    $ pytest

### Usage
The API has the following endpoints:

1. Register user: /register/ (POST)
2. Login: /login/ (POST)
3. User details: /users/ (GET, PUT)

You can test the API using any REST client such as Postman.

### Note
The API uses basic authentication for accessing user details. A token is generated during login, which can be used to access the user details.

### License
This project is licensed under the MIT License.


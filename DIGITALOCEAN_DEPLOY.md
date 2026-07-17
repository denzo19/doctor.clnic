# DigitalOcean Deployment

This app is ready to deploy from GitHub to DigitalOcean App Platform using the included `Dockerfile`.

## 1. Push to GitHub

Initialize Git if needed, commit the app, create a GitHub repository, then push this folder.

Do not commit `.env`. It is ignored by `.gitignore`.

## 2. Create the DigitalOcean app

1. Go to DigitalOcean App Platform.
2. Create a new app from the GitHub repository.
3. Choose Dockerfile deployment if DigitalOcean asks for the build type.
4. Set the HTTP port to `8080` if prompted.

## 3. Add environment variables

Set these in DigitalOcean App Platform:

```text
SECRET_KEY=your_long_random_secret
DB_HOST=your_database_host
DB_PORT=25060
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=doctor_health
OPENAI_API_KEY=your_openai_api_key
OPENAI_ID_CARD_MODEL=gpt-4o-mini
```

Use the values from your DigitalOcean Managed MySQL database for the database variables.

## 4. Database

Create a DigitalOcean Managed MySQL database, then import your local `doctor_health` database into it before using the app in production.

## 5. Uploads

`static/uploads/` is ignored because App Platform local disk is not permanent. For production, move uploaded ID-card files to DigitalOcean Spaces or another object storage service.

# Online-shop
This simple **Flask**-based website is a small online shop using **Stripe** API.

### Features:
- User login/registration.
- Displays items for sale.
- Working cart and checkout.
- Take payment from users (thanks to Stripe).

## Local installation
- Clone this repository.
- Create a new virtual environment.
- Install the required packages `pip install -r requirements.txt`
- Set your app's secret key as `SECRET_KEY` environment variable.
- Set your Stripe API key as `STRIPE_API_KEY` environment variable.
- Set your domain name as `DOMAIN` environment variable.
- Run main.py and use the URL displayed in the console to see the application in your browser.


## Deployment
For a deployment on Heroku you will need to adjust a config var :

- `DOMAIN` to let the app know where it should redirect user after Stripe checkout.


## Overview

![alt text](https://github.com/Julien-B-py/Online-shop/blob/main/img/demo.png?raw=true)

Deployed and hosted version available here: https://online-shop-jb.herokuapp.com/

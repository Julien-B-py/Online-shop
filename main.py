import json
import os
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps

import stripe

from flask import Flask, render_template, url_for, flash, session
from flask_login import login_user, current_user, UserMixin, LoginManager, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect

from forms import RegisterForm, LoginForm

domain_url = os.environ.get('DOMAIN')

stripe.api_key = os.environ.get("STRIPE_API_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# Define the life of the session object to timeout after 60 minutes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", 'sqlite:///users.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Define User data-model
# UserMixin to inherit is_authenticated and more properties and methods
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    # User Authentication fields
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    # User field
    cart = db.Column(db.String())


db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Simulate database for store products
store_df = pd.read_csv("store.csv")
store_data = store_df.to_dict('records')


# Customizing the login process to redirect to login page when login is required to access a specific URL.
@login_manager.unauthorized_handler
def unauthorized():
    flash("You need to login to perform this action.")
    return redirect(url_for('login'))


def manage_session(func):
    """Manages user session by creating a new user cart if session does not exists"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session or not session.get('user_cart'):
            # Setting session cart and cart items count
            session['user_cart'] = {}
            session['items_in_cart'] = sum(session.get('user_cart', {"count": 0}).values())
            session.modified = True
        return func(*args, **kwargs)

    return wrapper


# Inject new values into the template context
@app.context_processor
def inject_data():
    return {'year': datetime.now().year,
            'current_user': current_user, }


@app.route("/")
@manage_session
def home():
    """
    Main route displaying all items.
    Allows user to see items prices and add them to cart.
    """
    session['items_in_cart'] = sum(session.get('user_cart', {"count": 0}).values())
    session.modified = True
    return render_template("index.html", store_data=store_data)


@app.route("/add/<item_id>")
@manage_session
@login_required
def add_to_cart(item_id: str):
    """
    Route to add item to user cart.
        @param item_id: Specify the item id to add to user cart
        @type item_id: str
    """
    # Reading and updating session cart
    # Initialize item count value to 1 if not in cart already
    if item_id not in session.get('user_cart'):
        session['user_cart'][item_id] = 1

    # Increment item count by 1 if already in cart
    else:
        session['user_cart'][item_id] += 1

    # Save user cart in database
    user = current_user
    user.cart = json.dumps(session['user_cart'])
    db.session.commit()

    # Update cart items count
    session['items_in_cart'] = sum(session.get('user_cart', {"count": 0}).values())
    session.modified = True

    flash("The item was added to your shopping cart.")

    return redirect(url_for("home"))


@app.route("/remove/<item_id>")
@manage_session
@login_required
def remove_from_cart(item_id: str):
    """
    Route to remove item from user cart.
        @param item_id: Specify the item id to remove from user cart
        @type item_id: str
    """
    # If item in user cart remove it
    if item_id in session['user_cart']:
        del session['user_cart'][item_id]
        # Update cart items count
        session['items_in_cart'] = sum(session.get('user_cart', {"count": 0}).values())
        # Update user cart in database
        user = current_user
        user.cart = json.dumps(session['user_cart'])
        db.session.commit()

        session.modified = True
        flash("The selected item has been removed.")
        return redirect(url_for("cart"))
    # Redirect if url called manually
    return redirect(url_for("home"))


@app.route("/clear")
@manage_session
@login_required
def clear_cart():
    """
    Route to remove all items from user cart.
    """
    # If user cart has items clear it
    if session['user_cart']:
        session['user_cart'].clear()
        # Update cart items count
        session['items_in_cart'] = sum(session.get('user_cart', {"count": 0}).values())
        # Update user cart in database
        user = current_user
        user.cart = json.dumps(session['user_cart'])
        db.session.commit()

        session.modified = True
        flash("All items have been removed.")
    else:
        flash("Your cart is already empty.")
    return redirect(url_for("cart"))


@app.route("/cart")
@manage_session
@login_required
def cart():
    """
    Route to display user cart.
    Displays total price, items and items counts.
    """
    # Initialize two lists and an integer to display cart data, checkout data and total price in HTML
    final_cart = []
    checkout = []
    total = 0

    # Loop through all items in user cart
    for _id in session.get('user_cart', {}):

        # Loop through all items in "database"
        for item in store_data:

            # If item ids are matching
            if item.get("id") == int(_id):
                # Add a new dict to the final_cart list containing item id, name, price, image and count
                final_cart.append({"id": item.get("id"),
                                   "item": item.get("item"),
                                   "price": item.get("price"),
                                   "image": item.get("image"),
                                   "count": session['user_cart'].get(_id)})

                # Add a dict containing the item stripe price and associated the quantity to the list
                checkout.append({'price': item.get("stripe"), 'quantity': session['user_cart'].get(_id)})

                # Increment total cart price by item price multiplied by item count
                total += item.get("price") * session['user_cart'].get(_id)

    # Store checkout list in session to use it later
    session["checkout"] = checkout
    session.modified = True

    return render_template("cart.html", final_cart=final_cart, total=total)


@app.route('/checkout')
@manage_session
@login_required
def create_checkout_session():
    """
    Route to allow user payment.
    Checks items in user cart.
    Displays total price, items and items counts.
    """
    if not session['user_cart']:
        flash("Your cart is empty.")
        return redirect(url_for("cart"))

    try:
        # Create a Stripe Checkout Session
        # Use 4242 4242 4242 4242 card for testing
        checkout_session = stripe.checkout.Session.create(

            # Fill user email field automatically
            customer_email=current_user.email,

            # Define products to sell from user cart
            # Get the data we stored earlier to display products info and determine total price during checkout
            line_items=session["checkout"],
            payment_method_types=['card'],
            mode='payment',
            success_url=domain_url + "/success",
            cancel_url=domain_url + "/cancel",

        )

    except Exception as e:

        return str(e)

    return redirect(checkout_session.url, code=303)


@app.route('/cancel')
@manage_session
@login_required
def cancel_checkout():
    """Route called when user cancels checkout"""
    flash("Forgot to add something to your cart? Shop around then come back to pay!")
    return redirect(url_for("home"))


@app.route('/success')
@login_required
def checkout_success():
    """Route called when user payment is approved"""
    # Clear user cart data
    session.pop("user_cart")
    # Update cart items count
    session['items_in_cart'] = sum(session.get('user_cart', {"count": 0}).values())
    session.modified = True

    # Update user cart in database
    user = current_user
    user.cart = json.dumps(session.get('user_cart'))
    db.session.commit()

    return render_template("success.html")


@app.route('/register', methods=["GET", "POST"])
def register():
    """
    Route to create an user account.
    Checks if provided email address is not in use.
    Hashes user password and save user info in database.
    """
    form = RegisterForm()

    if form.validate_on_submit():

        # Check if a user already exists with the specified email address
        if User.query.filter_by(email=form.email.data).first():
            flash("Email address already in use.")
            flash("Sign-In or create an account with a different e-mail address.")
            return render_template("register.html", form=form)

        # Hashed password with salt
        secured_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=16
        )

        # Create a new user and save it in database
        user = User(
            name=form.name.data,
            email=form.email.data,
            password=secured_password,
            cart=json.dumps(session['user_cart']),
        )
        db.session.add(user)
        db.session.commit()
        # Login user right after
        login_user(user)

        flash("Account successfully created!")

        return redirect(url_for("home"))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """
    Route to login on an existing user account.
    Checks if provided email address is in database.
    Checks if provided password matches the saved password.
    Load user cart if exists.
    """
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Check if a user with that email exists
        user = User.query.filter_by(email=email).first()

        # If no user with that email
        if not user:
            flash('We cannot find an account with that email address')
            return redirect(url_for("login"))

        # If entered password doesnt match with the real user password
        if not check_password_hash(user.password, password):
            flash('Your password is incorrect.')
            return render_template("login.html", form=form)

        # Login user if everything above is not checked
        login_user(user)

        # Load user cart from database and store it in session
        session['user_cart'] = json.loads(user.cart)
        flash("Logged in successfully.")
        return redirect(url_for("home"))

    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    """Logout the user and clear the current session"""
    logout_user()
    # Clear session data
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

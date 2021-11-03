from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, EqualTo, Length


class RegisterForm(FlaskForm):
    name = StringField("Your name", validators=[DataRequired("Enter your name")])
    email = EmailField("Email", validators=[DataRequired("Enter your email")])
    password = PasswordField("Password",
                             validators=[DataRequired(" Enter your password"),
                                         Length(min=8,
                                                message="Passwords must be at least 8 characters.")])
    password_confirmation = PasswordField("Confirm your password",
                                          validators=[DataRequired(),
                                                      EqualTo(fieldname="password",
                                                              message="Passwords must match")])
    submit = SubmitField("Create your account")


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired("Enter your email")])
    password = PasswordField("Password",
                             validators=[DataRequired(" Enter your password")])

    submit = SubmitField("Sign-In")
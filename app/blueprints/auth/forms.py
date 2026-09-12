from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

VALID_USERNAME = Regexp(r"^[A-Za-zА-Яа-яЁё0-9_]+$", message="Только буквы, цифры и подчёркивание.")


class RegisterForm(FlaskForm):
    username = StringField(
        "Имя пользователя",
        validators=[DataRequired(), Length(min=3, max=32), VALID_USERNAME],
        render_kw={"placeholder": "Например, geniusfan", "autofocus": True},
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(), Length(min=6, max=128)],
        render_kw={"placeholder": "Минимум 6 символов"},
    )
    confirm = PasswordField(
        "Повторите пароль",
        validators=[DataRequired(), EqualTo("password", message="Пароли не совпадают")],
    )
    submit = SubmitField("Зарегистрироваться")


class LoginForm(FlaskForm):
    username = StringField(
        "Имя пользователя", validators=[DataRequired()], render_kw={"autofocus": True}
    )
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth.forms import LoginForm, RegisterForm
from app.blueprints.auth import bp
from app.extensions import db
from app.models import User


@bp.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tracks.my_tracks"))
    return render_template("auth/register.html", form=RegisterForm())


@bp.post("/register")
def register_post():
    form = RegisterForm()
    if not form.validate_on_submit():
        return render_template("auth/register.html", form=form), 400

    username = form.username.data.strip()
    exists = db.session.scalar(db.select(User).where(User.username == username))
    if exists:
        form.username.errors.append("Такое имя уже занято.")
        return render_template("auth/register.html", form=form), 400

    user = User(username=username)
    user.set_password(form.password.data)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    flash(f"Добро пожаловать, {user.username}!", "success")
    return redirect(url_for("tracks.my_tracks"))


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tracks.my_tracks"))
    return render_template("auth/login.html", form=LoginForm())


@bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        return render_template("auth/login.html", form=form), 400

    user = db.session.scalar(
        db.select(User).where(User.username == form.username.data.strip())
    )
    if user is None or not user.check_password(form.password.data):
        form.password.errors.append("Неверное имя пользователя или пароль.")
        return render_template("auth/login.html", form=form), 400

    login_user(user)
    next_url = url_for("tracks.my_tracks")
    flash(f"С возвращением, {user.username}!", "success")
    return redirect(next_url)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("auth.login"))
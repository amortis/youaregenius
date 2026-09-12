from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class SearchForm(FlaskForm):
    q = StringField(
        "Поиск",
        validators=[DataRequired(), Length(min=2, max=100)],
        render_kw={
            "placeholder": "Название трека или артист",
            "autofocus": True,
        },
    )
    submit = SubmitField("Искать")
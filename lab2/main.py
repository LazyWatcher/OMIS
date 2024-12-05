import atexit
from flask import Flask, render_template, url_for, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import signal

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agriculture.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Advice(db.Model):
    __tablename__ = 'Advice'
    advice_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    field_id = db.Column(db.Integer, db.ForeignKey('Field.field_id', ondelete='CASCADE', onupdate='CASCADE'))
    advice = db.Column(db.Text, nullable=False)

class Agronomist(db.Model):
    __tablename__ = 'Agronomist'
    agronomist_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    agronomist_name = db.Column(db.String(15), nullable=False)
    max_fields = db.Column(db.Integer, nullable=False)

class Plant(db.Model):
    __tablename__ = 'Plant'
    plant_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plant_name = db.Column(db.String(50), unique=True, nullable=False)
    humidity_norm = db.Column(db.Integer, nullable=False)
    pollution_norm = db.Column(db.Integer, nullable=False)
    temperature_norm = db.Column(db.Integer, nullable=False)
    soil_quality_norm = db.Column(db.Integer, nullable=False)
    counter = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.CheckConstraint('counter > 0', name='humidity_check'),
    )


class Field(db.Model):
    __tablename__ = 'Field'
    field_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('Plant.plant_id', ondelete='CASCADE', onupdate='CASCADE'))
    agronomist_id = db.Column(db.Integer, db.ForeignKey('Agronomist.agronomist_id', ondelete='CASCADE', onupdate='CASCADE'))
    counter = db.Column(db.Integer, db.ForeignKey('Plant.counter', ondelete='CASCADE', onupdate='CASCADE'))
    area = db.Column(db.Integer, nullable=False)
    humidity = db.Column(db.Integer, nullable=False)
    pollution = db.Column(db.Integer, nullable=False)
    temperature = db.Column(db.Integer, nullable=False)
    soil_quality = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=True)



    __table_args__ = (
        db.CheckConstraint('humidity BETWEEN 0 AND 10', name='humidity_correct'),
        db.CheckConstraint('pollution BETWEEN 0 AND 10', name='pollution_correct'),
        db.CheckConstraint('temperature BETWEEN 0 AND 10', name='temperature_correct'),
        db.CheckConstraint('soil_quality BETWEEN 0 AND 10', name='soil_quality_correct'),
        db.CheckConstraint("status IN ('grown', 'full', 'empty')", name='status_correct'),
        db.CheckConstraint('counter >= 0', name='humidity_correct'),
    )




@app.before_request
def check_and_update_fields():

    if not hasattr(app, '_initialized'):
        app._initialized = True
        fields = Field.query.all()


        for field in fields:
            if field.counter is None and field.plant_id is not None:
                plant = db.session.get(Plant, field.plant_id)
                if plant:
                    field.counter = plant.counter


            if field.plant_id is None:
                field.agronomist_id = None
                field.counter = None
                field.status = 'Пусто'

        db.session.commit()


def check_field_characteristics():
    fields = Field.query.all()

    for field in fields:
        if field.plant_id:
            plant = db.session.get(Plant, field.plant_id)
            if not plant:
                continue

            def add_advice_if_not_exists(field_id, message):
                existing_advice = Advice.query.filter_by(field_id=field_id, advice=message).first()
                if not existing_advice:
                    new_advice = Advice(field_id=field_id, advice=message)
                    db.session.add(new_advice)


            if field.temperature > plant.temperature_norm:
                add_advice_if_not_exists(field.field_id, "Температура высокая. Снизьте её")
            elif field.temperature < plant.temperature_norm:
                add_advice_if_not_exists(field.field_id, "Температура низкая. Повысите её")

            if field.humidity > plant.humidity_norm:
                add_advice_if_not_exists(field.field_id, "Влажность почвы высокая. Снизьте её.")
            elif field.humidity < plant.humidity_norm:
                add_advice_if_not_exists(field.field_id, "Влажность почвы низкая. Повысите её")


            if field.soil_quality < plant.soil_quality_norm:
                add_advice_if_not_exists(field.field_id, "Качество почвы недостаточно. Улучшите удобрения")


            if field.pollution > plant.pollution_norm:
                add_advice_if_not_exists(field.field_id, "Уровень загрязнения слишком высокий. Примите меры")


    db.session.commit()


@app.route('/')
def index():
    agronomist_count = Agronomist.query.count()
    field_count = Field.query.count()
    return render_template('init_view.html', agronomist_count=agronomist_count, field_count=field_count)


@app.route('/field')
def work():
    fields = Field.query.order_by(Field.field_id).all()
    plant_data = {plant.plant_id: plant for plant in Plant.query.all()}
    agronomist_data = {agronomist.agronomist_id: agronomist for agronomist in Agronomist.query.all()}

    return render_template('work_menu.html', fields=fields, plant_data=plant_data, agronomist_data=agronomist_data)


@app.route('/result')
def result_view():
    advice_data = Advice.query.order_by(Advice.field_id).all()
    return render_template('result_view.html', sorted_advice=advice_data)


@app.route('/field/<int:field_id>')
def field_info(field_id):

    field = Field.query.get_or_404(field_id)
    plant_name = None
    if field.plant_id:
        plant = db.session.get(Plant, field.plant_id)
        plant_name = plant.plant_name if plant else "Неизвестно"


    return render_template(
        'cell_info_view.html',
        field=field,
        plant_name=plant_name
    )

@app.route('/field/<int:field_id>/edit', methods=['GET', 'POST'])
def edit_field(field_id):
    field = Field.query.get_or_404(field_id)
    plant_name = None
    if field.plant_id:
        plant = db.session.get(Plant, field.plant_id)
        plant_name = plant.plant_name if plant else ""

    if request.method == 'POST':

        field.area = int(request.form.get('area', field.area))
        field.humidity = int(request.form.get('humidity', field.humidity))
        field.temperature = int(request.form.get('temperature', field.temperature))
        field.pollution = int(request.form.get('pollution', field.pollution))
        field.soil_quality = int(request.form.get('soil_quality', field.soil_quality))
        field.status = request.form.get('status', field.status)

        plant_name_form = request.form.get('plant_name', plant_name)
        if plant_name_form:
            plant = Plant.query.filter_by(plant_name=plant_name_form).first()
            field.plant_id = plant.plant_id if plant else None

        db.session.commit()
        return redirect(url_for('field_info', field_id=field_id))

    return render_template(
        'cell_edit_view.html',
        field=field,
        plant_name=plant_name
    )
@app.route('/wait', methods=['POST'])
def wait_action():
    data = request.get_json()
    wait_time = data.get('wait_time', 0)

    if wait_time > 0:
        fields = Field.query.filter(Field.counter > 0).all()
        for field in fields:
            field.counter = max(0, field.counter - wait_time)
            if field.counter == 0:
                field.status = 'Созрело'

        db.session.commit()

    return jsonify({'message': 'Операция выполнена'})

@app.route('/shutdown', methods=['POST'])
def shutdown():

    os.kill(os.getpid(), signal.SIGINT)
    return 'Server shutting down...'

def clear_advice_table():
    with app.app_context():
        db.session.query(Advice).delete()
        db.session.commit()

atexit.register(clear_advice_table)


if __name__ == "__main__":
    with app.app_context():
        check_field_characteristics()
    app.run(debug=True)
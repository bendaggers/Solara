from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ohlcv", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnownClosure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol",      models.CharField(max_length=20)),
                ("timeframe",   models.CharField(max_length=5)),
                ("time",        models.DateTimeField()),
                ("reason",      models.CharField(default="no_data", max_length=50)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ohlcv_known_closure",
                "ordering": ["symbol", "timeframe", "time"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="knownclosure",
            unique_together={("symbol", "timeframe", "time")},
        ),
    ]

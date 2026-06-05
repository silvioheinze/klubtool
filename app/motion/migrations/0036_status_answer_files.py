import os

import django.db.models.deletion
from django.db import migrations, models


def migrate_answer_pdf_to_answer_files(apps, schema_editor):
    MotionStatus = apps.get_model('motion', 'MotionStatus')
    MotionStatusAnswerFile = apps.get_model('motion', 'MotionStatusAnswerFile')

    for status_entry in MotionStatus.objects.exclude(answer_pdf='').exclude(answer_pdf__isnull=True):
        if not status_entry.answer_pdf:
            continue
        filename = os.path.basename(status_entry.answer_pdf.name)
        MotionStatusAnswerFile.objects.create(
            status_entry_id=status_entry.pk,
            file=status_entry.answer_pdf,
            filename=filename or 'answer.pdf',
        )


def reverse_migrate_answer_files(apps, schema_editor):
    MotionStatus = apps.get_model('motion', 'MotionStatus')
    MotionStatusAnswerFile = apps.get_model('motion', 'MotionStatusAnswerFile')

    for answer_file in MotionStatusAnswerFile.objects.select_related('status_entry').order_by('uploaded_at'):
        status_entry = answer_file.status_entry
        if not status_entry.answer_pdf:
            status_entry.answer_pdf = answer_file.file
            status_entry.save(update_fields=['answer_pdf'])


class Migration(migrations.Migration):

    dependencies = [
        ('motion', '0035_alter_inquiry_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MotionStatusAnswerFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='motion_answers/%Y/%m/%d/')),
                ('filename', models.CharField(max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('status_entry', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='answer_files',
                    to='motion.motionstatus',
                )),
            ],
            options={
                'verbose_name': 'Motion Status Answer File',
                'verbose_name_plural': 'Motion Status Answer Files',
                'ordering': ['uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='InquiryStatusAnswerFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='inquiry_answers/%Y/%m/%d/')),
                ('filename', models.CharField(max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('status_entry', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='answer_files',
                    to='motion.inquirystatus',
                )),
            ],
            options={
                'verbose_name': 'Inquiry Status Answer File',
                'verbose_name_plural': 'Inquiry Status Answer Files',
                'ordering': ['uploaded_at'],
            },
        ),
        migrations.RunPython(migrate_answer_pdf_to_answer_files, reverse_migrate_answer_files),
        migrations.RemoveField(
            model_name='motionstatus',
            name='answer_pdf',
        ),
    ]

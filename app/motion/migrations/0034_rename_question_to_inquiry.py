# Generated manually for Questions -> Inquiries rename

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('motion', '0033_motionstatus_answer_pdf'),
    ]

    operations = [
        migrations.RenameModel(old_name='Question', new_name='Inquiry'),
        migrations.RenameField(
            model_name='questionstatus',
            old_name='question',
            new_name='inquiry',
        ),
        migrations.RenameModel(old_name='QuestionStatus', new_name='InquiryStatus'),
        migrations.RenameField(
            model_name='questionattachment',
            old_name='question',
            new_name='inquiry',
        ),
        migrations.RenameModel(old_name='QuestionAttachment', new_name='InquiryAttachment'),
    ]

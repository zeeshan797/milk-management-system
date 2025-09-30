from django.db import models

# Create your models here.
class Customer(models.Model):
    acc_no = models.IntegerField(unique=True)
    customer_name = models.CharField(max_length=50)
    mobile_no = models.IntegerField(null = True, blank=True)

    def __str__(self):
        return f"{self.acc_no}({self.customer_name})"


class MilkEntry(models.Model):
    milk_type_choices = (("cow", "Cow"), ("buffalo", "Buffalo"))
    shift_choices = (("day", "Day"), ("evening", "Evening"))

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    acc_no = models.IntegerField(blank=True, null=True, editable=False)
    shift = models.CharField(max_length=50, choices = shift_choices)
    milk_type = models.CharField(max_length=50, choices=milk_type_choices)
    fat = models.FloatField()
    qnt = models.FloatField()
    amt = models.FloatField()
    date = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.acc_no = self.customer.acc_no
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.customer}"
    

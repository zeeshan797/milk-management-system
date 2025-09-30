from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from .models import Customer, MilkEntry
from .forms import CustomerForm, MilkEntryForm
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from datetime import datetime, timedelta, date
from django.contrib import messages
from django.http import JsonResponse

# Home/Dashboard View with Filtering
def home(request):
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    customer_id = request.GET.get('customer')
    
    # Start with all entries
    entries = MilkEntry.objects.select_related('customer')
    
    # Apply filters only if provided
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            entries = entries.filter(date__gte=from_date_obj)
        except ValueError:
            from_date = None
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            entries = entries.filter(date__lte=to_date_obj)
        except ValueError:
            to_date = None
    
    if customer_id:
        try:
            entries = entries.filter(customer_id=customer_id)
        except ValueError:
            pass
    
    # FIXED: If no filters, show last 30 days instead of just today
    if not from_date and not to_date and not customer_id:
        today = timezone.localdate()
        # last_30_days = timezone.localdate() - timedelta(days=30)
        entries = entries.filter(date = today)
        from_date = today.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    
    # Order entries
    entries = entries.order_by('-date', '-id')
    
    # Calculate totals
    totals = entries.aggregate(
        total_quantity=Sum('qnt'),
        total_amount=Sum('amt'),
        total_entries=Count('id'),
        # avg_fat=Avg('fat')
    )
    
    # Get entries for display
    recent_entries = entries[:15]
    
    # Get all customers
    customers = Customer.objects.all().order_by('customer_name')
    
    # Daily summary
    daily_summary = entries.values('date').annotate(
        daily_quantity=Sum('qnt'),
        daily_amount=Sum('amt'),
        entry_count=Count('id')
    ).order_by('-date')[:7]
    
    context = {
        'entries': recent_entries,
        'total_quantity': round(totals['total_quantity'] or 0, 2),
        'total_amount': round(totals['total_amount'] or 0, 2),
        'total_entries': totals['total_entries'] or 0,
        # 'avg_fat': round(totals['avg_fat'] or 0, 2),
        'customers': customers,
        'selected_customer': customer_id,
        'from_date': from_date,
        'to_date': to_date,
        'daily_summary': daily_summary,
    }
    return render(request, 'home.html', context)


# Customer Views (Enhanced)
class CustomerListView(ListView):
    model = Customer
    template_name = 'customers.html'
    context_object_name = 'customers'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add summary data for each customer
        customers_with_summary = []
        for customer in context['customers']:
            # Fix: Apply ordering BEFORE slicing
            recent_entries_queryset = customer.milkentry_set.order_by('-date', '-id')
            recent_entries = recent_entries_queryset[:5]  # Now slice after ordering
            
            total_amount = customer.milkentry_set.aggregate(Sum('amt'))['amt__sum'] or 0
            total_quantity = customer.milkentry_set.aggregate(Sum('qnt'))['qnt__sum'] or 0
            
            # Get last entry safely
            last_entry = recent_entries_queryset.first() if recent_entries_queryset.exists() else None
            
            customers_with_summary.append({
                'customer': customer,
                'total_amount': round(total_amount, 2),
                'total_quantity': round(total_quantity, 2),
                'recent_entries_count': len(recent_entries),
                'last_entry': last_entry
            })
        
        context['customers_with_summary'] = customers_with_summary
        return context


class CustomerCreateView(CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customer_form.html'
    success_url = reverse_lazy('customers')
    
    def form_valid(self, form):
        messages.success(self.request, f'Customer {form.instance.customer_name} created successfully!')
        return super().form_valid(form)

class CustomerUpdateView(UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customer_form.html'
    success_url = reverse_lazy('customers')
    
    def form_valid(self, form):
        messages.success(self.request, f'Customer {form.instance.customer_name} updated successfully!')
        return super().form_valid(form)

class CustomerDetailView(DetailView):
    model = Customer
    template_name = 'customer_detail.html'
    context_object_name = 'customer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object
        
        # Get filter parameters
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')
        
        # Default to last 10 days if no date provided
        if not from_date or not to_date:
            end_date = timezone.localdate()
            start_date = end_date - timedelta(days=9)
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')
        else:
            try:
                start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = timezone.localdate()
                start_date = end_date - timedelta(days=9)
                from_date = start_date.strftime('%Y-%m-%d')
                to_date = end_date.strftime('%Y-%m-%d')
        
        # Get milk entries for the date range
        milk_entries = customer.milkentry_set.filter(
            date__range=[start_date, end_date]
        ).order_by('-date', '-id')
        
        # Calculate totals
        totals = milk_entries.aggregate(
            total_amount=Sum('amt'),
            total_quantity=Sum('qnt'),
            total_entries=Count('id'),
            # avg_fat=Avg('fat')
        )
        
        # Group by date for better display
        entries_by_date = {}
        for entry in milk_entries:
            date_key = entry.date
            if date_key not in entries_by_date:
                entries_by_date[date_key] = {
                    'entries': [],
                    'daily_total': 0,
                    'daily_quantity': 0
                }
            entries_by_date[date_key]['entries'].append(entry)
            entries_by_date[date_key]['daily_total'] += entry.amt
            entries_by_date[date_key]['daily_quantity'] += entry.qnt
        
        # Overall customer statistics
        all_entries = customer.milkentry_set.all()
        overall_stats = all_entries.aggregate(
            lifetime_amount=Sum('amt'),
            lifetime_quantity=Sum('qnt'),
            lifetime_entries=Count('id'),
            # avg_fat=Avg('fat')
        )
        
        context.update({
            'milk_entries': milk_entries,
            'entries_by_date': entries_by_date,
            'total_amount': round(totals['total_amount'] or 0, 2),
            'total_quantity': round(totals['total_quantity'] or 0, 2),
            'total_entries': totals['total_entries'] or 0,
            # 'avg_fat': round(totals['avg_fat'] or 0, 2),
            'from_date': from_date,
            'to_date': to_date,
            'date_range_days': (end_date - start_date).days + 1,
            'overall_stats': overall_stats,
        })
        
        return context

def delete_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer_name = customer.customer_name
    customer.delete()
    messages.success(request, f'Customer {customer_name} deleted successfully!')
    return redirect('customers')
    

# Milk Entry Views (Enhanced)
class MilkEntryListView(ListView):
    model = MilkEntry
    template_name = 'entries.html'
    context_object_name = 'entries'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = MilkEntry.objects.select_related('customer').order_by('-date', '-id')
        
        # Apply filters
        customer_id = self.request.GET.get('customer')
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')
        milk_type = self.request.GET.get('milk_type')
        shift = self.request.GET.get('shift')
        
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if from_date:
            try:
                queryset = queryset.filter(date__gte=datetime.strptime(from_date, '%Y-%m-%d').date())
            except ValueError:
                pass
        if to_date:
            try:
                queryset = queryset.filter(date__lte=datetime.strptime(to_date, '%Y-%m-%d').date())
            except ValueError:
                pass
        if milk_type:
            queryset = queryset.filter(milk_type=milk_type)
        if shift:
            queryset = queryset.filter(shift=shift)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customers'] = Customer.objects.all().order_by('customer_name')
        context['selected_customer'] = self.request.GET.get('customer')
        context['from_date'] = self.request.GET.get('from_date')
        context['to_date'] = self.request.GET.get('to_date')
        context['selected_milk_type'] = self.request.GET.get('milk_type')
        context['selected_shift'] = self.request.GET.get('shift')
        
        # Calculate totals for filtered results
        filtered_entries = self.get_queryset()
        totals = filtered_entries.aggregate(
            total_amount=Sum('amt'),
            total_quantity=Sum('qnt'),
            total_entries=Count('id')
        )
        context['totals'] = totals
        
        return context

class MilkEntryCreateView(CreateView):
    model = MilkEntry
    form_class = MilkEntryForm
    template_name = 'entry_form.html'
    success_url = reverse_lazy('new_entry')
    
    def form_valid(self, form):
        messages.success(self.request, 'Milk entry created successfully!')
        return super().form_valid(form)

class MilkEntryUpdateView(UpdateView):
    model = MilkEntry
    form_class = MilkEntryForm
    template_name = 'entry_form.html'
    success_url = reverse_lazy('entries')
    
    def form_valid(self, form):
        messages.success(self.request, 'Milk entry updated successfully!')
        return super().form_valid(form)

class MilkEntryDetailView(DetailView):
    model = MilkEntry
    template_name = 'entry_detail.html'
    context_object_name = 'entry'

def delete_entry(request, pk):
    entry = get_object_or_404(MilkEntry, pk=pk)
    entry.delete()
    messages.success(request, 'Milk entry deleted successfully!')
    return redirect('entries')
    

# New Payment Summary View
def payment_summary(request):
    """View to show payment summary for all customers with 10-day calculation option"""
    
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    customer_id = request.GET.get('customer')
    
    # Default to last 10 days if no date provided
    if not from_date or not to_date:
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=9)
        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')
    else:
        try:
            start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = timezone.localdate()
            start_date = end_date - timedelta(days=9)
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')
    
    # Get base customer queryset
    customers_query = Customer.objects.all().order_by('customer_name')
    
    # NEW: Apply customer filter if specified
    if customer_id:
        try:
            customers_query = customers_query.filter(id=customer_id)
        except ValueError:
            customer_id = None
    
    # Get all customers with their payment data
    customers_data = []
    
    
    for customer in customers_query:
        entries = customer.milkentry_set.filter(
            date__range=[start_date, end_date]
        )
        
        totals = entries.aggregate(
            total_amount=Sum('amt'),
            total_quantity=Sum('qnt'),
            total_entries=Count('id')
        )
        
        if totals['total_entries'] or totals['total_entries']>0:  # Only include customers with entries
            customers_data.append({
                'customer': customer,
                'total_amount': round(totals['total_amount'] or 0, 2),
                'total_quantity': round(totals['total_quantity'] or 0, 2),
                'total_entries': totals['total_entries'] or 0,
                'last_entry_date': entries.order_by('-date').first().date if entries.exists() else None
            })
    
    # Sort by total amount (highest first)
    customers_data.sort(key=lambda x: x['total_amount'], reverse=True)
    
    # Calculate overall totals
    grand_total_amount = sum(data['total_amount'] for data in customers_data)
    grand_total_quantity = sum(data['total_quantity'] for data in customers_data)
    
    # Get all customers for the filter dropdown
    all_customers = Customer.objects.all().order_by('customer_name')


    context = {
        'customers_data': customers_data,
        'from_date': from_date,
        'to_date': to_date,
        'selected_customer': customer_id,
        'all_customers': all_customers,
        'date_range_days': (end_date - start_date).days + 1,
        'grand_total_amount': round(grand_total_amount, 2),
        'grand_total_quantity': round(grand_total_quantity, 2),
    }
    
    return render(request, 'payment_summary.html', context)

/**
 * static/js/dashboard-billing.js - Dashboard billing information
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the dashboard page with subscription tab
    const subscriptionTab = document.getElementById('subscription');
    if (!subscriptionTab) return;
    
    // Get auth token
    const token = localStorage.getItem('auth_token');
    if (!token) {
        window.location.href = '/login?redirect=dashboard';
        return;
    }
    
    // Get invoice container
    const invoicesContainer = document.getElementById('invoices-container');
    if (!invoicesContainer) return;
    
    // Load invoices
    loadInvoices();
    
    // Function to load invoices
    function loadInvoices() {
        fetch('/api/dashboard/subscription/invoices', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch invoices');
            }
            return response.json();
        })
        .then(data => {
            // Clear container
            invoicesContainer.innerHTML = '';
            
            if (!data || data.length === 0) {
                invoicesContainer.innerHTML = '<div class="alert alert-info">No invoices available yet.</div>';
                return;
            }
            
            // Create invoices table
            const table = document.createElement('table');
            table.className = 'table table-hover';
            
            // Create table header
            const thead = document.createElement('thead');
            thead.innerHTML = `
                <tr>
                    <th>Date</th>
                    <th>Invoice Number</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            `;
            
            // Create table body
            const tbody = document.createElement('tbody');
            
            data.forEach(invoice => {
                const tr = document.createElement('tr');
                
                // Format date
                const date = new Date(invoice.created);
                const formattedDate = date.toLocaleDateString('en-GB', { 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric'
                });
                
                // Format status
                const statusBadge = getStatusBadge(invoice.status);
                
                // Actions
                let actions = '';
                if (invoice.hosted_invoice_url) {
                    actions += `<a href="${invoice.hosted_invoice_url}" target="_blank" class="btn btn-sm btn-outline-primary me-2">View</a>`;
                }
                if (invoice.invoice_pdf) {
                    actions += `<a href="${invoice.invoice_pdf}" target="_blank" class="btn btn-sm btn-outline-secondary">PDF</a>`;
                }
                
                // Set row HTML
                tr.innerHTML = `
                    <td>${formattedDate}</td>
                    <td>${invoice.number || 'N/A'}</td>
                    <td>$${invoice.amount_due.toFixed(2)}</td>
                    <td>${statusBadge}</td>
                    <td>${actions}</td>
                `;
                
                tbody.appendChild(tr);
            });
            
            // Assemble table
            table.appendChild(thead);
            table.appendChild(tbody);
            
            // Add to container
            invoicesContainer.appendChild(table);
        })
        .catch(error => {
            console.error('Error fetching invoices:', error);
            invoicesContainer.innerHTML = '<div class="alert alert-danger">Failed to load invoices. Please try again later.</div>';
        });
    }
    
    // Helper function to get status badge
    function getStatusBadge(status) {
        const badges = {
            'paid': '<span class="badge bg-success">Paid</span>',
            'open': '<span class="badge bg-warning text-dark">Open</span>',
            'uncollectible': '<span class="badge bg-danger">Uncollectible</span>',
            'void': '<span class="badge bg-secondary">Void</span>',
            'draft': '<span class="badge bg-info">Draft</span>'
        };
        
        return badges[status] || `<span class="badge bg-secondary">${status}</span>`;
    }
    
    // Helper function to format currency
    function formatCurrency(amount, currency = 'gbp') {
        // Get currency symbol
        const symbols = {
            'usd': '$',
            'eur': '€',
            'gbp': '£',
            'jpy': '¥'
        };
        
        const symbol = symbols[currency.toLowerCase()] || '';
        
        // Format amount
        return `${symbol}${parseFloat(amount).toFixed(2)}`;
    }
});

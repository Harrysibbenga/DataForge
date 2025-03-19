/**
 * static/js/pricing.js - JavaScript for the pricing page with Stripe integration
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get auth token from localStorage
    const token = localStorage.getItem('auth_token');
    
    // Get plan buttons
    const planButtons = document.querySelectorAll('[data-plan]');
    
    // Check if user already has a subscription (to show correct button state)
    if (token) {
        fetch('/api/payment/subscription', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            // If no subscription or error, just continue without modifying buttons
            return null;
        })
        .then(data => {
            if (data && data.subscription) {
                const currentPlan = data.subscription.plan;
                
                // Update button display based on current plan
                planButtons.forEach(button => {
                    const plan = button.getAttribute('data-plan');
                    
                    if (plan === currentPlan) {
                        button.textContent = 'Current Plan';
                        button.classList.remove('btn-primary', 'btn-dark');
                        button.classList.add('btn-success');
                        button.disabled = true;
                    } else if (isPlanUpgrade(currentPlan, plan)) {
                        button.textContent = 'Upgrade';
                    } else {
                        button.textContent = 'Downgrade';
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error fetching subscription:', error);
        });
    }

    // Handle plan button clicks
    planButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const plan = this.getAttribute('data-plan');
            
            // Check if user is logged in
            if (!token) {
                // Redirect to login if not authenticated
                window.location.href = `/login?redirect=pricing&plan=${plan}`;
                return;
            }
            
            // Show loading state
            const originalText = this.textContent;
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
            
            // Determine if this is a new subscription, upgrade, or downgrade
            if (this.classList.contains('btn-success')) {
                // Already on this plan - do nothing
                this.disabled = false;
                this.textContent = originalText;
                return;
            }
            
            // Create checkout session or change plan
            fetch('/api/payment/create-checkout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ tier: plan })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'redirect' || data.status === 'scheduled') {
                    // Show message for scheduled downgrade
                    showAlert(data.message, 'success');
                    
                    // Update button state
                    this.disabled = false;
                    this.textContent = 'Scheduled';
                } else if (data.checkout_url) {
                    // Redirect to Stripe checkout
                    window.location.href = data.checkout_url;
                } else {
                    // Show error
                    showAlert('There was an error processing your request. Please try again.', 'danger');
                    this.disabled = false;
                    this.textContent = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('An error occurred. Please try again.', 'danger');
                this.disabled = false;
                this.textContent = originalText;
            });
        });
    });
    
    // Helper function to determine if a plan change is an upgrade
    function isPlanUpgrade(currentPlan, newPlan) {
        const planRanking = {
            'free': 0,
            'basic': 1,
            'pro': 2,
            'enterprise': 3
        };
        
        return planRanking[newPlan] > planRanking[currentPlan];
    }
    
    // Helper function to show alerts
    function showAlert(message, type) {
        const alertContainer = document.getElementById('alert-container');
        if (!alertContainer) {
            // Create alert container if it doesn't exist
            const container = document.createElement('div');
            container.id = 'alert-container';
            container.className = 'container mt-3';
            document.querySelector('.py-5').insertAdjacentElement('afterend', container);
        }
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        document.getElementById('alert-container').appendChild(alert);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    }
    
    // Check URL parameters for messages
    const urlParams = new URLSearchParams(window.location.search);
    const message = urlParams.get('message');
    const type = urlParams.get('type') || 'info';
    
    if (message) {
        showAlert(decodeURIComponent(message), type);
        
        // Remove parameters from URL without refreshing the page
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

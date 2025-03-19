/**
 * static/js/dashboard-subscription.js - Dashboard subscription management 
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
    
    // Elements
    const currentPlanName = document.getElementById('current-plan-name');
    const planName = document.getElementById('plan-name');
    const planPrice = document.getElementById('plan-price');
    const planStatus = document.getElementById('plan-status');
    const nextBillingDate = document.getElementById('next-billing-date');
    const planConversions = document.getElementById('plan-conversions');
    const planFileLimit = document.getElementById('plan-file-limit');
    const planApi = document.getElementById('plan-api');
    const planSupport = document.getElementById('plan-support');
    
    const basicPlanBtn = document.getElementById('downgrade-basic-btn');
    const enterprisePlanBtn = document.getElementById('upgrade-enterprise-btn');
    const cancelSubscriptionBtn = document.getElementById('cancel-subscription-btn');
    
    // Fetch subscription data
    fetchSubscriptionData();
    
    // Set up event listeners
    if (basicPlanBtn) {
        basicPlanBtn.addEventListener('click', function() {
            handlePlanChange('basic', 'downgrade');
        });
    }
    
    if (enterprisePlanBtn) {
        enterprisePlanBtn.addEventListener('click', function() {
            handlePlanChange('enterprise', 'upgrade');
        });
    }
    
    if (cancelSubscriptionBtn) {
        cancelSubscriptionBtn.addEventListener('click', function() {
            handleCancelSubscription();
        });
    }
    
    // Function to fetch subscription data
    function fetchSubscriptionData() {
        fetch('/api/payment/subscription', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch subscription data');
            }
            return response.json();
        })
        .then(data => {
            // Update subscription UI
            updateSubscriptionUI(data);
        })
        .catch(error => {
            console.error('Error fetching subscription data:', error);
            showAlert('Failed to load subscription data. Please try again later.', 'danger');
        });
    }
    
    // Function to format date
    function formatDate(dateString) {
        if (!dateString) return 'N/A';
        
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    }
    
    // Function to update subscription UI
    function updateSubscriptionUI(data) {
        const subscription = data.subscription;
        const stripeData = data.stripe || {};
        
        // Update plan details
        if (currentPlanName) currentPlanName.textContent = (subscription.plan || 'Free').charAt(0).toUpperCase() + (subscription.plan || 'free').slice(1);
        if (planName) planName.textContent = (subscription.plan || 'Free').charAt(0).toUpperCase() + (subscription.plan || 'free').slice(1);
        
        // Set price based on plan
        if (planPrice) {
            const prices = {
                'free': '$0/month',
                'basic': '£9.99/month',
                'pro': '£24.99/month',
                'enterprise': '£99.99/month'
            };
            planPrice.textContent = prices[subscription.plan] || '$0/month';
        }
        
        // Update status
        if (planStatus) {
            planStatus.textContent = subscription.is_active ? 'Active' : 'Inactive';
            planStatus.className = 'badge ' + (subscription.is_active ? 'bg-success' : 'bg-danger');
        }
        
        // Next billing date
        if (nextBillingDate) nextBillingDate.textContent = formatDate(subscription.end_date);
        
        // Plan features
        if (planConversions) {
            const conversionsMap = {
                'free': '5 per day',
                'basic': '100 per month',
                'pro': '500 per month',
                'enterprise': 'Unlimited'
            };
            planConversions.textContent = conversionsMap[subscription.plan] || 'N/A';
        }
        
        if (planFileLimit) {
            planFileLimit.textContent = `${subscription.file_size_limit_mb}MB`;
        }
        
        if (planApi) {
            const apiMap = {
                'free': 'No API access',
                'basic': 'API access',
                'pro': 'Advanced API access',
                'enterprise': 'Full API access'
            };
            planApi.textContent = apiMap[subscription.plan] || 'N/A';
        }
        
        if (planSupport) {
            const supportMap = {
                'free': 'Community support',
                'basic': 'Email support',
                'pro': 'Priority support',
                'enterprise': 'Dedicated support'
            };
            planSupport.textContent = supportMap[subscription.plan] || 'N/A';
        }
        
        // Update button states based on current plan
        updatePlanButtons(subscription.plan);
        
        // Load subscription history if available
        loadSubscriptionHistory();
    }
    
    // Function to update plan buttons based on current plan
    function updatePlanButtons(currentPlan) {
        // Plan ranking
        const planRanking = {
            'free': 0,
            'basic': 1,
            'pro': 2,
            'enterprise': 3
        };
        
        // Update basic plan button
        if (basicPlanBtn) {
            if (currentPlan === 'basic') {
                basicPlanBtn.textContent = 'Current Plan';
                basicPlanBtn.disabled = true;
                basicPlanBtn.classList.remove('btn-outline-primary');
                basicPlanBtn.classList.add('btn-success');
            } else if (planRanking[currentPlan] < planRanking['basic']) {
                basicPlanBtn.textContent = 'Upgrade';
                basicPlanBtn.disabled = false;
                basicPlanBtn.classList.remove('btn-outline-primary');
                basicPlanBtn.classList.add('btn-primary');
            } else {
                basicPlanBtn.textContent = 'Downgrade';
                basicPlanBtn.disabled = false;
            }
        }
        
        // Update enterprise plan button
        if (enterprisePlanBtn) {
            if (currentPlan === 'enterprise') {
                enterprisePlanBtn.textContent = 'Current Plan';
                enterprisePlanBtn.disabled = true;
                enterprisePlanBtn.classList.remove('btn-dark');
                enterprisePlanBtn.classList.add('btn-success');
            } else {
                enterprisePlanBtn.textContent = 'Upgrade';
                enterprisePlanBtn.disabled = false;
            }
        }
        
        // Update cancel button
        if (cancelSubscriptionBtn) {
            if (currentPlan === 'free') {
                cancelSubscriptionBtn.disabled = true;
            } else {
                cancelSubscriptionBtn.disabled = false;
            }
        }
    }
    
    // Function to handle plan change
    function handlePlanChange(plan, action) {
        if (!confirm(`Are you sure you want to ${action} to the ${plan.charAt(0).toUpperCase() + plan.slice(1)} plan?`)) {
            return;
        }
        
        // Disable button during request
        const button = action === 'upgrade' ? enterprisePlanBtn : basicPlanBtn;
        const originalText = button.textContent;
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        
        // Call API to change plan
        fetch('/api/payment/change-plan', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_plan: plan })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to change plan');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'redirect' && data.action === 'checkout') {
                // Redirect to checkout
                window.location.href = `/api/payment/create-checkout?tier=${plan}`;
            } else if (data.status === 'scheduled') {
                // Show success message for scheduled downgrade
                showAlert(data.message, 'success');
                button.textContent = 'Scheduled';
                // Refresh data
                fetchSubscriptionData();
            } else if (data.status === 'success') {
                // Show success message for immediate change
                showAlert(data.message, 'success');
                // Refresh data
                fetchSubscriptionData();
            } else {
                // Show generic success message
                showAlert('Plan change processed successfully.', 'success');
                // Reset button
                button.disabled = false;
                button.textContent = originalText;
                // Refresh data
                fetchSubscriptionData();
            }
        })
        .catch(error => {
            console.error('Error changing plan:', error);
            showAlert('Failed to change plan. Please try again later.', 'danger');
            // Reset button
            button.disabled = false;
            button.textContent = originalText;
        });
    }
    
    // Function to handle subscription cancellation
    function handleCancelSubscription() {
        const atPeriodEnd = confirm('Would you like to cancel your subscription at the end of the current billing period? Click OK to cancel at period end, or Cancel to cancel immediately.');
        
        if (!confirm(`Are you sure you want to cancel your subscription? ${atPeriodEnd ? 'You will still have access until the end of your billing period.' : 'Your access will end immediately.'}`)) {
            return;
        }
        
        // Disable button during request
        const originalText = cancelSubscriptionBtn.textContent;
        cancelSubscriptionBtn.disabled = true;
        cancelSubscriptionBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        
        // Call API to cancel subscription
        fetch('/api/payment/cancel-subscription', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ at_period_end: atPeriodEnd })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to cancel subscription');
            }
            return response.json();
        })
        .then(data => {
            // Show success message
            showAlert(data.message || 'Subscription cancelled successfully.', 'success');
            // Refresh data
            fetchSubscriptionData();
            // Reset button
            cancelSubscriptionBtn.disabled = false;
            cancelSubscriptionBtn.textContent = originalText;
        })
        .catch(error => {
            console.error('Error cancelling subscription:', error);
            showAlert('Failed to cancel subscription. Please try again later.', 'danger');
            // Reset button
            cancelSubscriptionBtn.disabled = false;
            cancelSubscriptionBtn.textContent = originalText;
        });
    }
    
    // Function to load subscription history
    function loadSubscriptionHistory() {
        const historyContainer = document.getElementById('subscription-history-container');
        if (!historyContainer) return;
        
        fetch('/api/dashboard/subscription/history', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch subscription history');
            }
            return response.json();
        })
        .then(data => {
            // Clear container
            historyContainer.innerHTML = '';
            
            if (!data || data.length === 0) {
                historyContainer.innerHTML = '<div class="alert alert-info">No subscription history available.</div>';
                return;
            }
            
            // Create history list
            const list = document.createElement('ul');
            list.className = 'list-group';
            
            data.forEach(item => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                
                // Format action for display
                let actionDisplay = item.action.replace(/_/g, ' ');
                actionDisplay = actionDisplay.charAt(0).toUpperCase() + actionDisplay.slice(1);
                
                // Create badge for action
                const actionBadge = document.createElement('span');
                actionBadge.className = `badge ${getActionBadgeClass(item.action)} me-2`;
                actionBadge.textContent = actionDisplay;
                
                // Create content
                const content = document.createElement('div');
                
                // Format date
                const date = new Date(item.action_date);
                const formattedDate = date.toLocaleDateString('en-US', { 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
                
                // Set content HTML
                content.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            ${actionBadge.outerHTML}
                            ${item.previous_plan ? `Changed from <strong>${item.previous_plan}</strong> to <strong>${item.plan}</strong>` : `Plan: <strong>${item.plan}</strong>`}
                        </div>
                        <small class="text-muted">${formattedDate}</small>
                    </div>
                `;
                
                // Add metadata if available
                if (item.metadata && Object.keys(item.metadata).length > 0) {
                    const metadataDiv = document.createElement('div');
                    metadataDiv.className = 'mt-2 small text-muted';
                    
                    // Format metadata
                    if (item.metadata.effective_date) {
                        metadataDiv.innerHTML += `Effective date: ${formatDate(item.metadata.effective_date)}<br>`;
                    }
                    
                    if (item.metadata.downgrade_to) {
                        metadataDiv.innerHTML += `Scheduled downgrade to: ${item.metadata.downgrade_to}<br>`;
                    }
                    
                    content.appendChild(metadataDiv);
                }
                
                li.appendChild(content);
                list.appendChild(li);
            });
            
            historyContainer.appendChild(list);
        })
        .catch(error => {
            console.error('Error fetching subscription history:', error);
            historyContainer.innerHTML = '<div class="alert alert-danger">Failed to load subscription history.</div>';
        });
    }
    
    // Helper function to get badge class for action
    function getActionBadgeClass(action) {
        const classes = {
            'created': 'bg-success',
            'updated': 'bg-primary',
            'downgrade_scheduled': 'bg-warning text-dark',
            'downgraded': 'bg-info',
            'cancelled': 'bg-danger',
            'subscription_created': 'bg-success',
            'subscription_updated': 'bg-primary',
            'subscription_cancelled': 'bg-danger'
        };
        
        return classes[action] || 'bg-secondary';
    }
    
    // Helper function to show alerts
    function showAlert(message, type) {
        const alertContainer = document.getElementById('subscription-alert-container');
        if (!alertContainer) return;
        
        // Clear existing alerts
        alertContainer.innerHTML = '';
        
        // Create alert
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertContainer.appendChild(alert);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    }
});

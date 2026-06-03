// static/js/main.js

// Global variables
let currentPage = 1;
const itemsPerPage = 10;

// Wait for DOM to load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();
    
    // Load user requests if on dashboard
    if (document.getElementById('requestsTable')) {
        loadUserRequests();
    }
    
    // Setup form validation
    setupFormValidation();
    
    // Setup real-time notifications
    setupNotifications();
});

// Initialize Bootstrap tooltips
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Load user requests via AJAX
async function loadUserRequests(page = 1) {
    try {
        const response = await fetch('/my-requests');
        const requests = await response.json();
        
        if (requests.length > 0) {
            displayRequests(requests, page);
            setupPagination(requests.length);
        } else {
            showNoRequestsMessage();
        }
    } catch (error) {
        console.error('Error loading requests:', error);
        showErrorMessage('Failed to load requests');
    }
}

// Display requests in table
function displayRequests(requests, page) {
    const tableBody = document.getElementById('requestsTable');
    if (!tableBody) return;
    
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const paginatedRequests = requests.slice(start, end);
    
    tableBody.innerHTML = '';
    
    paginatedRequests.forEach(request => {
        const row = document.createElement('tr');
        
        // Status badge class
        let statusClass = 'bg-secondary';
        if (request.status === 'pending') statusClass = 'bg-warning';
        else if (request.status === 'approved') statusClass = 'bg-info';
        else if (request.status === 'completed') statusClass = 'bg-success';
        else if (request.status === 'rejected') statusClass = 'bg-danger';
        
        row.innerHTML = `
            <td><strong>${request.reference}</strong></td>
            <td>${request.service_name}</td>
            <td><span class="badge ${statusClass}">${request.status.toUpperCase()}</span></td>
            <td>${request.submitted_at}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="viewRequestDetails('${request.reference}')">
                    <i class="fas fa-eye"></i> View
                </button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

// Setup pagination
function setupPagination(totalItems) {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    const pagination = document.getElementById('pagination');
    if (!pagination) return;
    
    pagination.innerHTML = '';
    
    for (let i = 1; i <= totalPages; i++) {
        const pageItem = document.createElement('li');
        pageItem.className = `page-item ${i === currentPage ? 'active' : ''}`;
        pageItem.innerHTML = `<a class="page-link" href="#" onclick="changePage(${i})">${i}</a>`;
        pagination.appendChild(pageItem);
    }
}

// Change page
async function changePage(page) {
    currentPage = page;
    await loadUserRequests(page);
}

// Show no requests message
function showNoRequestsMessage() {
    const tableBody = document.getElementById('requestsTable');
    if (tableBody) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4">
                    <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                    <p>No service requests found.</p>
                    <a href="/services" class="btn btn-primary btn-sm">Submit Your First Request</a>
                </td>
            </tr>
        `;
    }
}

// Show error message
function showErrorMessage(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.container').prepend(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Show success message
function showSuccessMessage(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.container').prepend(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// View request details
async function viewRequestDetails(referenceNumber) {
    try {
        const response = await fetch(`/track-request/${referenceNumber}`);
        const request = await response.json();
        
        // Show modal with request details
        const modalHtml = `
            <div class="modal fade" id="requestModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Request Details: ${request.reference_number}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Service:</strong> ${request.service_name}</p>
                            <p><strong>Status:</strong> ${request.status}</p>
                            <p><strong>Submitted:</strong> ${request.submitted_at}</p>
                            <p><strong>Details:</strong> ${request.details}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('requestModal');
        if (existingModal) existingModal.remove();
        
        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('requestModal'));
        modal.show();
    } catch (error) {
        console.error('Error fetching request details:', error);
        showErrorMessage('Could not load request details');
    }
}

// Setup form validation
function setupFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

// Setup notifications (polling every 30 seconds)
function setupNotifications() {
    if (document.getElementById('notificationBell')) {
        setInterval(checkNotifications, 30000);
    }
}

// Check for new notifications
async function checkNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const notifications = await response.json();
        
        if (notifications.length > 0) {
            updateNotificationBadge(notifications.length);
        }
    } catch (error) {
        console.error('Error checking notifications:', error);
    }
}

// Update notification badge
function updateNotificationBadge(count) {
    const badge = document.getElementById('notificationBadge');
    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'inline-block' : 'none';
    }
}

// Search and filter requests
function filterRequests() {
    const searchTerm = document.getElementById('searchInput')?.value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter')?.value;
    
    if (!searchTerm && !statusFilter) {
        loadUserRequests();
        return;
    }
    
    // Client-side filtering (you can also implement server-side)
    const rows = document.querySelectorAll('#requestsTable tr');
    rows.forEach(row => {
        let show = true;
        
        if (searchTerm && !row.textContent.toLowerCase().includes(searchTerm)) {
            show = false;
        }
        
        if (statusFilter && statusFilter !== 'all') {
            const statusCell = row.querySelector('.badge');
            if (statusCell && !statusCell.textContent.toLowerCase().includes(statusFilter)) {
                show = false;
            }
        }
        
        row.style.display = show ? '' : 'none';
    });
}

// Export data to CSV
function exportToCSV() {
    const table = document.getElementById('requestsTable');
    if (!table) return;
    
    const rows = table.querySelectorAll('tr');
    const csvData = [];
    
    // Get headers
    const headers = ['Reference Number', 'Service Name', 'Status', 'Submitted Date'];
    csvData.push(headers.join(','));
    
    // Get data
    rows.forEach(row => {
        const rowData = [];
        const cells = row.querySelectorAll('td');
        for (let i = 0; i < 4; i++) {
            if (cells[i]) {
                let text = cells[i].innerText.replace(/,/g, ';');
                rowData.push(text);
            }
        }
        if (rowData.length > 0) {
            csvData.push(rowData.join(','));
        }
    });
    
    // Download CSV
    const blob = new Blob([csvData.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `digiserve_requests_${new Date().toISOString().slice(0,19)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    
    showSuccessMessage('Report exported successfully!');
}

// Auto-refresh dashboard data
let refreshInterval;
function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(() => {
        if (document.getElementById('requestsTable')) {
            loadUserRequests(currentPage);
        }
    }, 60000); // Refresh every minute
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}

// Start auto-refresh on dashboard
if (document.getElementById('requestsTable')) {
    startAutoRefresh();
}

// Stop auto-refresh when leaving page
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});
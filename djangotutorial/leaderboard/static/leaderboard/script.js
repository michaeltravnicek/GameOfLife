function openTab(evt, tabName) {
    const tabContents = document.querySelectorAll(".tab-content");
    const tabButtons = document.querySelectorAll(".tab-button");

    tabContents.forEach(tc => tc.style.display = "none");
    tabButtons.forEach(tb => tb.classList.remove("active"));

    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.classList.add("active");
}

function loadUser(userId) {
    const content = document.getElementById("leaderboard");
    if (!content) return;
    content.classList.add("fade-out");

    const url = `/api/user/${userId}/`;

    setTimeout(() => {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                const rows = data.actions.map(action => `
                    <tr>
                        <td>${escapeHtml(action.event__name)}</td>
                        <td>${escapeHtml(action.event__place)}</td>
                        <td>${new Date(action.event__date).toLocaleDateString('cs-CZ')}</td>
                        <td class="text-right font-mono">${action.user_points}</td>
                    </tr>
                `).join('');

                content.innerHTML = `
                    <div class="user-header flex items-center justify-between mb-6">
                        <button class="back-button" onclick="loadLeaderboard()">← Zpět</button>
                    </div>
                    <h1 class="section-title text-center mb-8">${escapeHtml(data.user_name)}</h1>
                    <div class="overflow-x-auto">
                        <table class="yolo-table user-table">
                            <colgroup>
                                <col>
                                <col style="width: 25%;">
                                <col style="width: 20%;">
                                <col style="width: 15%;">
                            </colgroup>
                            <thead>
                                <tr>
                                    <th>Akce</th>
                                    <th>Lokace</th>
                                    <th>Datum</th>
                                    <th class="text-right">Body</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                `;
                content.classList.remove("fade-out");
                content.classList.add("fade-in");
            })
            .catch(err => console.error(err));
    }, 300);
}

function loadLeaderboard() {
    const content = document.getElementById("leaderboard");
    if (content) content.classList.add("fade-out");
    setTimeout(() => location.reload(), 100);
}

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("event-modal");
    if (!modal) return;

    const modalImage = document.getElementById("modal-image");
    const modalName = document.getElementById("modal-name");
    const modalPlace = document.getElementById("modal-place");
    const modalDescription = document.getElementById("modal-description");
    const modalDate = document.getElementById("modal-date");
    const closeBtn = modal.querySelector(".close");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");

    let images = [];
    let currentIndex = 0;

    document.querySelectorAll(".event-card").forEach(card => {
        card.addEventListener("click", async function () {
            const name = card.querySelector(".card-title, h2")?.innerText || "";
            const place = card.querySelector(".event-place")?.innerText || "";
            const description = card.querySelector(".description")?.innerText || "";
            const date = card.querySelector(".event-date")?.innerText || "";
            const eventId = card.dataset.eventId;

            if (!eventId) return;

            try {
                const response = await fetch(`/api/events/${eventId}/images/`);
                const data = await response.json();
                images = data.images || [];
                currentIndex = 0;
                showImage(currentIndex);
            } catch (e) {
                console.error("Nepodařilo se načíst obrázky:", e);
                images = [];
                showImage(0);
            }

            modalName.innerText = name;
            if (modalPlace) modalPlace.innerText = place;
            modalDescription.innerText = description;
            modalDate.innerText = date;
            modal.classList.add("show");
        });
    });

    function showImage(index) {
        if (images.length > 0) {
            modalImage.src = images[index];
            modalImage.style.display = "block";
            prevBtn.classList.toggle("hidden", index === 0);
            nextBtn.classList.toggle("hidden", index + 1 === images.length);
        } else {
            prevBtn.classList.add("hidden");
            nextBtn.classList.add("hidden");
            modalImage.src = "";
            modalImage.style.display = "none";
        }
    }

    prevBtn?.addEventListener("click", function () {
        if (!images.length) return;
        currentIndex = (currentIndex - 1 + images.length) % images.length;
        showImage(currentIndex);
    });

    nextBtn?.addEventListener("click", function () {
        if (!images.length) return;
        currentIndex = (currentIndex + 1) % images.length;
        showImage(currentIndex);
    });

    closeBtn?.addEventListener("click", () => modal.classList.remove("show"));
    window.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.remove("show");
    });
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") modal.classList.remove("show");
    });
});

function animateLeaderboard() {
    const rows = document.querySelectorAll('#leaderboard-table tbody tr');
    rows.forEach((row) => {
        row.style.opacity = '';
        row.style.transform = '';
        row.style.animation = 'none';
    });
    document.querySelector('#leaderboard-table')?.offsetHeight;
    rows.forEach((row, index) => {
        row.style.animation = `fadeInUp 0.5s ease-out ${index * 0.035}s both`;
    });
}

window.addEventListener('load', function () {
    const container = document.getElementById('leaderboard');
    if (!container) return;
    const lastUpdate = container.dataset.lastUpdate;
    const stored = localStorage.getItem('leaderboard_last_update');
    if (lastUpdate && lastUpdate !== stored) {
        animateLeaderboard();
        localStorage.setItem('leaderboard_last_update', lastUpdate);
    }
});

function filterLeaderboard() {
    const input = document.getElementById('search-bar');
    if (!input) return;
    const filter = input.value.toLowerCase();

    const activeTab = document.querySelector('.tab-content[style*="display: block"]') || document.getElementById('total');
    if (!activeTab) return;
    const rows = activeTab.querySelectorAll('tbody tr');

    rows.forEach((row) => {
        const nameCell = row.querySelector('.user-name');
        if (!nameCell) return;
        const name = nameCell.textContent.toLowerCase();
        const matches = filter === '' || name.includes(filter);
        row.style.display = matches ? '' : 'none';
        if (matches) {
            row.style.removeProperty('opacity');
            row.style.removeProperty('transform');
            row.style.removeProperty('animation');
        }
    });
}

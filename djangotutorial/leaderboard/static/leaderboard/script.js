function openTab(evt, tabName) {
    document.querySelectorAll(".tab-content").forEach(tc => tc.style.display = "none");
    document.querySelectorAll(".tab-button").forEach(tb => tb.classList.remove("active"));
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
            .then(r => r.json())
            .then(data => {
                const rows = (data.actions || []).map(action => `
                    <div class="lb-row" style="cursor: default;">
                        <span class="rank">📅</span>
                        <span class="name">
                            <strong>${escapeHtml(action.event__name)}</strong>
                            <br>
                            <span style="font-size: 13px; color: var(--gol-text-muted);">
                                ${escapeHtml(action.event__place)} · ${new Date(action.event__date).toLocaleDateString('cs-CZ')}
                            </span>
                        </span>
                        <span class="points">+${action.user_points}</span>
                    </div>
                `).join('');

                content.innerHTML = `
                    <div class="user-header">
                        <button class="back-button" onclick="loadLeaderboard()">← Zpět</button>
                    </div>
                    <h1 class="section-title text-center">${escapeHtml(data.user_name)}</h1>
                    <div style="max-width: 720px; margin: 0 auto;">${rows || '<p class="text-muted text-center">Žádné akce.</p>'}</div>
                `;
                content.classList.remove("fade-out");
                content.classList.add("fade-in");
            })
            .catch(err => console.error(err));
    }, 200);
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

function filterLeaderboard() {
    const input = document.getElementById('search-bar');
    if (!input) return;
    const filter = input.value.toLowerCase();

    const activeTab = document.querySelector('.tab-content[style*="display: block"]') || document.getElementById('total');
    if (!activeTab) return;

    activeTab.querySelectorAll('.lb-row').forEach(row => {
        const nameEl = row.querySelector('.user-name') || row.querySelector('.name');
        if (!nameEl) return;
        const match = filter === '' || nameEl.textContent.toLowerCase().includes(filter);
        row.style.display = match ? '' : 'none';
    });
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

    document.querySelectorAll(".event-card[data-event-id]").forEach(card => {
        const innerLink = card.querySelector('a[href]');
        if (innerLink) return;
        card.addEventListener("click", async function () {
            const name = card.querySelector(".card-title, h2, h3")?.innerText || "";
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
                console.error(e);
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
            prevBtn?.classList.toggle("hidden", index === 0);
            nextBtn?.classList.toggle("hidden", index + 1 === images.length);
        } else {
            prevBtn?.classList.add("hidden");
            nextBtn?.classList.add("hidden");
            modalImage.src = "";
            modalImage.style.display = "none";
        }
    }

    prevBtn?.addEventListener("click", () => {
        if (!images.length) return;
        currentIndex = (currentIndex - 1 + images.length) % images.length;
        showImage(currentIndex);
    });
    nextBtn?.addEventListener("click", () => {
        if (!images.length) return;
        currentIndex = (currentIndex + 1) % images.length;
        showImage(currentIndex);
    });
    closeBtn?.addEventListener("click", () => modal.classList.remove("show"));
    window.addEventListener("click", (e) => { if (e.target === modal) modal.classList.remove("show"); });
    window.addEventListener("keydown", (e) => { if (e.key === "Escape") modal.classList.remove("show"); });
});

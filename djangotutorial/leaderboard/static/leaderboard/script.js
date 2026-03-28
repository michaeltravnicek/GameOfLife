
function openTab(evt, tabName) {
    const tabContents = document.querySelectorAll(".tab-content");
    const tabButtons = document.querySelectorAll(".tab-button");

    tabContents.forEach(tc => tc.style.display = "none");
    tabButtons.forEach(tb => tb.classList.remove("active"));

    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.classList.add("active");
}

function showSection(sectionId, event) {
    document.querySelectorAll('.container').forEach(function(section) {
        section.classList.add('hidden');
    });
    document.getElementById(sectionId).classList.remove('hidden');

    document.querySelectorAll('.menu-item').forEach(function(item) {
        item.classList.remove('active');
    });
    event.target.classList.add('active');
}

function loadUser(userId) {
    const content = document.getElementById("leaderboard");
    content.classList.add("fade-out");

    setTimeout(() => {
        fetch(`/api/user/${userId}/`)
            .then(response => response.json())
            .then(data => {
                console.log(data)
                content.innerHTML = `
                    <div class="user-header">
                        <button class="back-button" onclick="loadLeaderboard()">Back</button>
                    </div>
                    <h1 class="center-title">${data.user_name}</h1>
                    <table class="user-table">
                        <colgroup>
                            <col style="width: auto;">
                            <col style="width: 25%;">
                            <col style="width: 20%;">
                            <col style="width: 10%;">
                        </colgroup>
                        <tr>
                            <th>Akce</th>
                            <th>Lokace</th>
                            <th>Datum</th>
                            <th>Body</th>
                        </tr>
                        ${data.actions.map(action => `
                            <tr>
                                <td>${action.event__name}</td>
                                <td>${action.event__place}</td>
                                <td>${new Date(action.event__date).toLocaleDateString('cs-CZ')}</td>
                                <td>${action.user_points}</td>
                            </tr>
                        `).join('')}
                    </table>
                `;
                content.classList.remove("fade-out");
                content.classList.add("fade-in");
            })
            .catch(err => console.error(err));
    }, 500);
}

function loadLeaderboard() {
    const content = document.getElementById("leaderboard");
    content.classList.add("fade-out");

    setTimeout(() => {
        location.reload(); 
    }, 100);
}

document.addEventListener("DOMContentLoaded", function() {
    const modal = document.getElementById("event-modal");
    if (!modal) {
        return;
    }

    const modalImage = document.getElementById("modal-image");
    const modalName = document.getElementById("modal-name");
    const modalPlace = document.getElementById("modal-place");
    const modalDescription = document.getElementById("modal-description");
    const modalDate = document.getElementById("modal-date");
    const closeBtn = document.querySelector(".close");

    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");

    let images = [];
    let currentIndex = 0;

    document.querySelectorAll(".event-card").forEach(card => {
        card.addEventListener("click", async function() {
            const name = card.querySelector("h2")?.innerText || "";
            const place = card.querySelector(".event-place")?.innerText || "";
            const description = card.querySelector(".description")?.innerText || "";
            const date = card.querySelector(".event-date")?.innerText || "";
            const eventId = card.dataset.eventId;

            if (!eventId) {
                console.error("❌ Chybí data-event-id na kartě!");
                return;
            }

            try {
                const response = await fetch(`/api/events/${eventId}/images/`);
                const data = await response.json();
                images = data.images || [];

                currentIndex = 0;
                showImage(currentIndex);
            } catch (e) {
                console.error("❌ Nepodařilo se načíst obrázky:", e);
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
            if (index == 0) {
                if (index + 1 == images.length) {
                    prevBtn.classList.add("hidden");
                    nextBtn.classList.add("hidden");
                } else {
                    prevBtn.classList.add("hidden")
                    nextBtn.classList.remove("hidden")
                }
            } else if (index + 1 == images.length) {
                console.log("dobry jinak?")
                prevBtn.classList.remove("hidden");
                nextBtn.classList.add("hidden");
            } else {
                prevBtn.classList.remove("hidden");
                nextBtn.classList.remove("hidden");
            }
             
        } else {
            console.log("Co se deje kurva")
            prevBtn.classList.add("hidden");
            nextBtn.classList.add("hidden");
            modalImage.src = "";
            modalImage.style.display = "none";
        }
    }

    prevBtn?.addEventListener("click", function() {
        if (images.length > 0) {
            currentIndex = (currentIndex - 1 + images.length) % images.length;
            showImage(currentIndex);
        }
    });

    nextBtn?.addEventListener("click", function() {
        if (images.length > 0) {
            currentIndex = (currentIndex + 1) % images.length;
            showImage(currentIndex);
        }
    });

    closeBtn?.addEventListener("click", function() {
        modal.classList.remove("show");
    });

    window.addEventListener("click", function(event) {
        if (event.target === modal) {
            modal.classList.remove("show");
        }
    });
});

let lastScrollTop = 0;
let scrollUpCount = 0;
let scrollDistanceThreshold = 20;
let hideThreshold = 50;
const menu = document.querySelector('.menu-container');

window.addEventListener('scroll', function() {
    let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    let delta = lastScrollTop - scrollTop;

    if (scrollTop < hideThreshold) {
        menu.style.top = "0";
        scrollUpCount = 0;
    } 
    else if (delta > scrollDistanceThreshold) {
        scrollUpCount++;
        if (scrollUpCount >= 3) {
            menu.style.top = "0";
        }
    } 
    else if (delta < -scrollDistanceThreshold) {
        menu.style.top = "-100px";
        scrollUpCount = 0;
    }

    lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
});

// Funkce pro spuštění animace při aktualizaci leaderboardu
function animateLeaderboard() {
    const rows = document.querySelectorAll('#leaderboard-table tr');

    // Nastav počáteční stav před animací
    rows.forEach((row, index) => {
        if (index === 0) return;
        row.style.opacity = '0';
        row.style.transform = 'translateY(20px)';
        row.style.animation = 'none';
    });

    // Force reflow
    document.querySelector('#leaderboard-table')?.offsetHeight;

    rows.forEach((row, index) => {
        if (index === 0) return;
        row.style.animation = `fadeInUp 0.6s ease-in-out ${index * 0.05}s both`;
    });
}

// Spuštění animace při načtení stránky
window.addEventListener('load', animateLeaderboard);

// Příklad: Spuštění animace po aktualizaci leaderboardu
function updateLeaderboard() {
    // Zde by byl kód pro aktualizaci leaderboardu (např. AJAX volání)

    // Po aktualizaci spustíme animaci
    animateLeaderboard();
}

// Úprava filtrování pro odstranění všech animací
function filterLeaderboard() {
    const input = document.getElementById('search-bar');
    const filter = input.value.toLowerCase();
    const rows = document.querySelectorAll('#leaderboard-table tr');

    let visibleRowIndex = 0; // Index pro střídavé zbarvení

    rows.forEach((row, index) => {
        if (index === 0) return; // Přeskočit hlavičku tabulky
        const nameCell = row.querySelector('.user-name');
        if (nameCell) {
            const name = nameCell.textContent.toLowerCase();
            const matches = name.includes(filter);

            // Zobrazení nebo skrytí řádku
            row.style.display = matches || filter === '' ? '' : 'none';

            // Pokud je řádek viditelný, nastavíme střídavé zbarvení
            if (matches || filter === '') {
                row.style.backgroundColor = visibleRowIndex % 2 === 0 ? '#f9f9f9' : '#f0f0f0'; // Upravená tmavá barva
                visibleRowIndex++;
            }

            // Odstranění všech animací
            row.style.animation = 'none';
        }
    });
}

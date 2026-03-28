window.addEventListener('load', function(){
    document.querySelectorAll('table tr td').forEach((td, i) => {
        td.style.animationDelay = (i * 0.05) + "s";
    });
});

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

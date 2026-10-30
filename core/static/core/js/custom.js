document.addEventListener('DOMContentLoaded', () => {
    const searchDropdown = document.getElementById('headerTopSearchDropdown');
    const searchToggle = document.querySelector('[aria-controls="headerTopSearchDropdown"]');
    if (searchDropdown && searchToggle) {
        new MutationObserver(() => {
            searchToggle.setAttribute('aria-expanded', String(searchDropdown.classList.contains('show')));
        }).observe(searchDropdown, { attributes: true, attributeFilter: ['class'] });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && searchDropdown.classList.contains('show')) {
                searchDropdown.classList.remove('show');
                searchToggle.focus();
            }
        });
    }

    const navigation = document.getElementById('primary-navigation');
    const toggle = document.querySelector('[aria-controls="primary-navigation"]');

    if (!navigation || !toggle) return;

    navigation.addEventListener('show.bs.collapse', () => {
        toggle.setAttribute('aria-label', toggle.dataset.labelClose);
    });

    navigation.addEventListener('hidden.bs.collapse', () => {
        toggle.setAttribute('aria-label', toggle.dataset.labelOpen);
    });

    navigation.addEventListener('click', (event) => {
        if (!event.target.closest('a') || !navigation.classList.contains('show')) return;

        bootstrap.Collapse.getOrCreateInstance(navigation, { toggle: false }).hide();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape' || !navigation.classList.contains('show')) return;

        bootstrap.Collapse.getOrCreateInstance(navigation, { toggle: false }).hide();
        toggle.focus();
    });
});

document.addEventListener('DOMContentLoaded', function () {
    const backToTop = document.querySelector('.back-to-top');

    if (!backToTop) {
        return;
    }

    const toggleVisibility = () => {
        if (window.scrollY > 260) {
            backToTop.classList.add('show');
        } else {
            backToTop.classList.remove('show');
        }
    };

    toggleVisibility();
    window.addEventListener('scroll', toggleVisibility);
});

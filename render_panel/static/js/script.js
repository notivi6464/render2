document.addEventListener('DOMContentLoaded', function () {
    console.log("Render panel initialized!");
    
    // Örnek: Kategori menüsünü genişletmek için basit bir işlev
    var categoryMenu = document.querySelector('nav ul li:nth-child(3) > ul');
    var categoryLink = document.querySelector('nav ul li:nth-child(3) > a');
    
    categoryLink.addEventListener('click', function(event) {
        event.preventDefault();
        if (categoryMenu.style.display === 'block') {
            categoryMenu.style.display = 'none';
        } else {
            categoryMenu.style.display = 'block';
        }
    });
});

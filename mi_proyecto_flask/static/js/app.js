document.addEventListener('DOMContentLoaded', function() {
    // Cargar datos del inventario al iniciar
    cargarInventario();
    
    // Event listeners
    document.getElementById('calcular').addEventListener('click', calcularTotal);
    document.getElementById('vender').addEventListener('click', realizarVenta);
    document.getElementById('buscar').addEventListener('input', filtrarSucursales);
});

// Variables globales para almacenar el inventario
let inventario = {
    sucursales: [],
    casa_matriz: {}
};

// Función para cargar inventario desde la API
function cargarInventario() {
    fetch('/api/inventario')
        .then(response => response.json())
        .then(data => {
            inventario = data;
            mostrarInventario(data);
        })
        .catch(error => console.error('Error al cargar inventario:', error));
}

// Función para mostrar inventario en la página
function mostrarInventario(data) {
    const sucursalesContainer = document.getElementById('sucursales-container');
    const casaMatrizContainer = document.getElementById('casa-matriz-container');
    
    // Limpiar contenedores
    sucursalesContainer.innerHTML = '';
    casaMatrizContainer.innerHTML = '';
    
    // Mostrar sucursales
    data.sucursales.forEach(sucursal => {
        const divSucursal = document.createElement('div');
        divSucursal.className = 'sucursal';
        divSucursal.innerHTML = `${sucursal.nombre}<br>Cant: ${sucursal.cantidad} | Precio: ${sucursal.precio}`;
        sucursalesContainer.appendChild(divSucursal);
    });
    
    // Mostrar casa matriz
    const divCasaMatriz = document.createElement('div');
    divCasaMatriz.className = 'sucursal';
    divCasaMatriz.innerHTML = `Casa Matriz<br>Cant: ${data.casa_matriz.cantidad} | Precio: ${data.casa_matriz.precio}`;
    casaMatrizContainer.appendChild(divCasaMatriz);
}

// Función para filtrar sucursales al buscar
function filtrarSucursales() {
    const textoBusqueda = document.getElementById('buscar').value.toLowerCase();
    const sucursalesContainer = document.getElementById('sucursales-container');
    
    sucursalesContainer.innerHTML = '';
    
    inventario.sucursales.forEach(sucursal => {
        if (sucursal.nombre.toLowerCase().includes(textoBusqueda)) {
            const divSucursal = document.createElement('div');
            divSucursal.className = 'sucursal';
            divSucursal.innerHTML = `${sucursal.nombre}<br>Cant: ${sucursal.cantidad} | Precio: ${sucursal.precio}`;
            sucursalesContainer.appendChild(divSucursal);
        }
    });
}

// Función para calcular el total
function calcularTotal() {
    const sucursalId = document.getElementById('sucursal').value;
    const cantidad = parseInt(document.getElementById('cantidad').value);
    
    if (!cantidad || isNaN(cantidad) || cantidad <= 0) {
        alert('Por favor ingrese una cantidad válida');
        return;
    }
    
    let precio = 0;
    
    if (sucursalId === 'casa_matriz') {
        precio = inventario.casa_matriz.precio;
    } else {
        const sucursal = inventario.sucursales.find(s => s.id == sucursalId);
        if (sucursal) {
            precio = sucursal.precio;
        }
    }
    
    const total = precio * cantidad;
    document.getElementById('total').textContent = total;
    
    // Convertir a USD
    fetch('/api/transformar_usd', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ precio_clp: total })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('totalUSD').textContent = data.precio_usd;
    })
    .catch(error => console.error('Error al convertir a USD:', error));
}

// Función para realizar venta
function realizarVenta() {
    const sucursalId = parseInt(document.getElementById('sucursal').value);
    const cantidad = parseInt(document.getElementById('cantidad').value);
    
    if (isNaN(cantidad) || cantidad <= 0) {
        alert('Por favor ingrese una cantidad válida');
        return;
    }
    
    if (isNaN(sucursalId)) {
        alert('No se puede vender desde la Casa Matriz');
        return;
    }
    
    fetch('/api/vender', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sucursal_id: sucursalId, cantidad: cantidad })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error) });
        }
        return response.json();
    })
    .then(data => {
        alert('Venta realizada correctamente');
        cargarInventario(); // Recargar inventario
    })
    .catch(error => {
        alert('Error: ' + error.message);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    cargarInventario();
    document.getElementById('calcular').addEventListener('click', calcularTotal);
    document.getElementById('vender').addEventListener('click', iniciarPago);
    document.getElementById('buscar').addEventListener('input', filtrarSucursales);
});

let inventario = {
    sucursales: [],
    casa_matriz: {}
};

// Carga el inventario desde el backend y actualiza la vista y el select
function cargarInventario() {
    // Agrega parámetro anti-cache
    fetch(`/api/inventario?timestamp=${new Date().getTime()}`)
        .then(response => response.json())
        .then(data => {
            inventario = data;
            mostrarInventario(data);
            actualizarSelectSucursales(data.sucursales);
        })
        .catch(error => console.error('Error:', error));
}

// Agrega evento para recargar al regresar a la página
window.addEventListener('pageshow', function(event) {
    if (event.persisted) { // Si viene de cache
        cargarInventario();
    }
});

// Muestra la lista de sucursales y la casa matriz en pantalla
function mostrarInventario(data) {
    const sucursalesContainer = document.getElementById('sucursales-container');
    const casaMatrizContainer = document.getElementById('casa-matriz-container');
    sucursalesContainer.innerHTML = '';
    casaMatrizContainer.innerHTML = '';

    // Mostrar sucursales
    data.sucursales.forEach(sucursal => {
        const divSucursal = document.createElement('div');
        divSucursal.className = 'sucursal';
        divSucursal.innerHTML = `
            <strong>${sucursal.nombre}</strong><br>
            Cantidad: ${sucursal.cantidad} | Precio: ${sucursal.precio}
        `;
        sucursalesContainer.appendChild(divSucursal);
    });

    // Mostrar casa matriz
    if (data.casa_matriz) {
        const divCasaMatriz = document.createElement('div');
        divCasaMatriz.className = 'sucursal';
        divCasaMatriz.innerHTML = `
            <strong>Casa Matriz</strong><br>
            Cantidad: ${data.casa_matriz.cantidad} | Precio: ${data.casa_matriz.precio}
        `;
        casaMatrizContainer.appendChild(divCasaMatriz);
    }
}

// Actualiza el select de sucursales según los datos reales
function actualizarSelectSucursales(sucursales) {
    const select = document.getElementById('sucursal');
    select.innerHTML = '';
    sucursales.forEach(sucursal => {
        const option = document.createElement('option');
        option.value = sucursal.id;
        option.textContent = sucursal.nombre;
        select.appendChild(option);
    });
    /** Agrega la opción de Casa Matriz
    const optionMatriz = document.createElement('option');
    optionMatriz.value = 'casa_matriz';
    optionMatriz.textContent = 'Casa Matriz';
    select.appendChild(optionMatriz);  */
}

// Permite filtrar sucursales por nombre
function filtrarSucursales() {
    const textoBusqueda = document.getElementById('buscar').value.toLowerCase();
    const sucursalesFiltradas = inventario.sucursales.filter(sucursal =>
        sucursal.nombre.toLowerCase().includes(textoBusqueda)
    );
    mostrarInventario({sucursales: sucursalesFiltradas, casa_matriz: inventario.casa_matriz});
}

// Calcula el total en CLP y USD según la sucursal seleccionada y la cantidad
async function calcularTotal() {
    const sucursalId = document.getElementById('sucursal').value;
    const cantidad = parseInt(document.getElementById('cantidad').value);

    if (!cantidad || isNaN(cantidad) || cantidad <= 0) {
        alert('Ingrese cantidad válida');
        return;
    }

    let precio = 0;
    if (sucursalId === 'casa_matriz') {
        precio = inventario.casa_matriz.precio;
    } else {
        const sucursal = inventario.sucursales.find(s => s.id == sucursalId);
        precio = sucursal ? sucursal.precio : 0;
    }

    const total = precio * cantidad;
    document.getElementById('total').textContent = total;

    // Calcula el total en USD
    try {
        const usdResponse = await fetch('/api/transformar_usd', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({precio_clp: total})
        });
        const usdData = await usdResponse.json();
        document.getElementById('totalUSD').textContent = usdData.precio_usd;
    } catch (error) {
        document.getElementById('totalUSD').textContent = '-';
        console.error('Error al convertir a USD:', error);
    }
}

// Inicia el pago con Transbank
async function iniciarPago() {
    const sucursalId = document.getElementById('sucursal').value;
    const cantidad = parseInt(document.getElementById('cantidad').value);
    const total = parseFloat(document.getElementById('total').textContent);

    if (isNaN(total) || total <= 0) {
        alert('Calcule el total primero');
        return;
    }

    try {
        const response = await fetch('/webpay/iniciar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                total: total,
                sucursal_id: sucursalId,
                cantidad: cantidad
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Error al iniciar el pago');
        }
        
        const data = await response.json();
        if (data.url) {
            window.location.href = data.url;
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}



window.addEventListener('pageshow', function(event) {
    cargarInventario();
});

async function vender() {
    const sucursalId = document.getElementById('sucursal').value;
    const cantidad = parseInt(document.getElementById('cantidad').value);

    try {
        const response = await fetch('/api/vender', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                sucursal_id: sucursalId,
                cantidad: cantidad
            })
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Error desconocido');
        }

        alert(data.mensaje);
        cargarInventario();  // Actualiza el inventario en pantalla

    } catch (error) {
        alert(error.message);
        // O redirige a la página de error con el mensaje
        window.location.href = `/venta-fallida?error=${encodeURIComponent(error.message)}`;
    }
}
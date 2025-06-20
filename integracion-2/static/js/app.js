document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos del DOM
    const sucursalesContainer = document.getElementById('sucursales-container');
    const casaMatrizContainer = document.getElementById('casa-matriz-container');
    const sucursalSelect = document.getElementById('sucursal');
    const cantidadInput = document.getElementById('cantidad');
    const calcularBtn = document.getElementById('calcular');
    const venderBtn = document.getElementById('vender');
    const totalClpSpan = document.getElementById('total');
    const totalUsdSpan = document.getElementById('totalUSD');
    
    let inventarioData = {}; // Para guardar los datos del inventario y acceder a ellos fácilmente

    // Función para cargar el inventario desde la API
    async function cargarInventario() {
        try {
            const response = await fetch('/api/inventario');
            if (!response.ok) throw new Error('No se pudo obtener el inventario.');
            inventarioData = await response.json();

            renderizarInventario();
        } catch (error) {
            console.error('Error al cargar el inventario:', error);
            sucursalesContainer.innerHTML = '<p>Error al cargar datos.</p>';
        }
    }

    // Función para dibujar el inventario en el HTML
    function renderizarInventario() {
        // Limpiar contenedores y selector
        sucursalesContainer.innerHTML = '';
        casaMatrizContainer.innerHTML = '';
        sucursalSelect.innerHTML = '';

        // Renderizar sucursales
        inventarioData.sucursales.forEach(s => {
            const sucursalDiv = document.createElement('div');
            sucursalDiv.className = 'sucursal-item';
            // Añadimos un ID único al span de la cantidad para poder actualizarlo
            sucursalDiv.innerHTML = `
                <strong>${s.nombre}</strong>
                <p>Cantidad: <span id="stock-sucursal_${s.id}">${s.cantidad}</span></p>
                <p>Precio: $${s.precio}</p>
            `;
            sucursalesContainer.appendChild(sucursalDiv);

            const option = document.createElement('option');
            option.value = s.id;
            option.textContent = s.nombre;
            sucursalSelect.appendChild(option);
        });

        // Renderizar Casa Matriz
        const cm = inventarioData.casa_matriz;
        // Añadimos un ID único al span de la cantidad
        casaMatrizContainer.innerHTML = `
            <p>Cantidad: <span id="stock-casa_matriz">${cm.cantidad}</span></p>
            <p>Precio: $${cm.precio}</p>
        `;
        const optionCm = document.createElement('option');
        optionCm.value = 'casa_matriz';
        optionCm.textContent = 'Casa Matriz';
        sucursalSelect.appendChild(optionCm);
    }
    
    // Función para conectar al stream de eventos del servidor (SSE)
    function conectarSSE() {
        console.log("Conectando al stream de eventos de stock (SSE)...");
        const eventSource = new EventSource("/api/stock-stream");

        eventSource.onmessage = function(event) {
            const stockUpdate = JSON.parse(event.data);
            console.log("SSE Recibido:", stockUpdate);

            // Buscar el elemento del DOM por su ID único
            const stockElement = document.getElementById(`stock-${stockUpdate.id}`);

            if (stockElement) {
                // Actualizar la cantidad en la interfaz
                stockElement.textContent = stockUpdate.cantidad;
                
                // Aplicar un efecto visual para resaltar el cambio
                stockElement.classList.add('stock-updated');
                
                // Mostrar una alerta al usuario
                alert(`¡Alerta de Stock! El inventario de '${stockUpdate.nombre}' ha cambiado a ${stockUpdate.cantidad}.`);

                // Quitar el efecto visual después de un momento
                setTimeout(() => {
                    stockElement.classList.remove('stock-updated');
                }, 1500);
            }
        };
        
        eventSource.onerror = function(err) {
            console.error("Error en la conexión EventSource. Intentando reconectar...", err);
            eventSource.close();
            // Opcional: intentar reconectar manualmente después de un tiempo
            setTimeout(conectarSSE, 5000); 
        };
    }

    // Lógica de los botones
    calcularBtn.addEventListener('click', async () => {
        const selectedId = sucursalSelect.value;
        const cantidad = parseInt(cantidadInput.value, 10);

        if (!cantidad || cantidad <= 0) {
            alert('Por favor, ingrese una cantidad válida.');
            return;
        }

        let precioUnitario = 0;
        if (selectedId === 'casa_matriz') {
            precioUnitario = inventarioData.casa_matriz.precio;
        } else {
            const sucursal = inventarioData.sucursales.find(s => s.id == selectedId);
            precioUnitario = sucursal.precio;
        }

        const totalClp = precioUnitario * cantidad;
        totalClpSpan.textContent = totalClp;
        totalUsdSpan.textContent = 'Calculando...';

        try {
            const response = await fetch('/api/transformar_usd', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ precio_clp: totalClp })
            });
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            totalUsdSpan.textContent = data.precio_usd;
        } catch (error) {
            totalUsdSpan.textContent = 'Error';
            console.error('Error al convertir a USD:', error);
        }
    });

    venderBtn.addEventListener('click', async () => {
        const total = parseFloat(totalClpSpan.textContent);
        if (isNaN(total) || total <= 0) {
            alert('Por favor, calcule el total primero.');
            return;
        }

        const ventaData = {
            total: total,
            sucursal_id: sucursalSelect.value,
            cantidad: parseInt(cantidadInput.value, 10)
        };

        try {
            const response = await fetch('/webpay/iniciar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(ventaData)
            });
            const data = await response.json();
            if (data.url) {
                // Redirigir al usuario a la página de pago de Transbank
                window.location.href = data.url;
            } else {
                throw new Error(data.error || 'Error desconocido al iniciar la venta.');
            }
        } catch (error) {
            alert(`Error al procesar la venta: ${error.message}`);
            console.error('Error en la venta:', error);
        }
    });

    // Iniciar todo
    cargarInventario();
    conectarSSE();
});
async function importCSV(e) {
    e.preventDefault();
    const fileInput = document.getElementById('csvFile');
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.innerText = "Importing...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/questions/import", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (data.status === "ok") {
            alert(`Successfully imported ${data.imported} questions!`);
            window.location.reload();
        } else {
            alert("Import failed: " + (data.detail || "Unknown error"));
        }
    } catch (err) {
        console.error(err);
        alert("Upload failed. Server might be down.");
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
        fileInput.value = "";
    }
}

async function addQuestion(e) {
    e.preventDefault();
    const payload = {
        question_type: document.getElementById('q_type').value,
        question_text: document.getElementById('q_text').value,
        point_value: parseInt(document.getElementById('q_points').value) || 0,
        sort_order: parseInt(document.getElementById('q_order').value) || 0,
        media_url: document.getElementById('q_media').value || null
    };

    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;

    try {
        const res = await fetch("/api/questions", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            window.location.reload();
        } else {
            alert("Error adding question.");
            btn.disabled = false;
        }
    } catch (err) {
        console.error(err);
        btn.disabled = false;
    }
}

async function deleteQuestion(id) {
    if (!confirm("Are you sure you want to delete this question? This cannot be undone.")) return;
    try {
        const res = await fetch(`/api/questions/${id}`, { method: "DELETE" });
        if (res.ok) {
            const el = document.getElementById(`q-${id}`);
            if (el) {
                el.style.opacity = '0';
                setTimeout(() => el.remove(), 300);
            }
            const countEl = document.getElementById('qCount');
            countEl.innerText = Math.max(0, parseInt(countEl.innerText) - 1);
        } else {
            alert("Error deleting question.");
        }
    } catch (err) {
        console.error(err);
    }
}

function openEditModal(id) {
    const q = questionsData[id];
    if (!q) return;
    
    document.getElementById('edit_id').value = id;
    document.getElementById('edit_type').value = q.type;
    document.getElementById('edit_text').value = q.text;
    document.getElementById('edit_points').value = q.points;
    document.getElementById('edit_order').value = q.order;
    document.getElementById('edit_media').value = q.media;
    
    document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
}

async function submitEdit(e) {
    e.preventDefault();
    const id = document.getElementById('edit_id').value;
    const payload = {
        question_type: document.getElementById('edit_type').value,
        question_text: document.getElementById('edit_text').value,
        point_value: parseInt(document.getElementById('edit_points').value) || 0,
        sort_order: parseInt(document.getElementById('edit_order').value) || 0,
        media_url: document.getElementById('edit_media').value || null
    };

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.innerText = "Saving...";
    btn.disabled = true;

    try {
        const res = await fetch(`/api/questions/${id}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            window.location.reload();
        } else {
            alert("Error updating question.");
            btn.innerText = originalText;
            btn.disabled = false;
        }
    } catch (err) {
        console.error(err);
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // 处理包上传
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            const formData = new FormData();
            formData.append('packageName', document.getElementById('packageName').value);
            formData.append('version', document.getElementById('version').value);
            formData.append('description', document.getElementById('description').value);
            formData.append('packageFile', document.getElementById('packageFile').files[0]);

            try {
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    alert('Package uploaded successfully!');
                    window.location.href = '/';
                } else {
                    alert('Upload failed. Please try again.');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Upload failed. Please try again.');
            }
        });
    }

    // 处理版本删除
    document.querySelectorAll('.delete-version').forEach(button => {
        button.addEventListener('click', async function () {
            if (confirm('Are you sure you want to delete this version?')) {
                const packageName = this.dataset.package;
                const version = this.dataset.version;

                try {
                    const response = await fetch(`/pypi/${packageName}/${version}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Delete failed. Please try again.');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Delete failed. Please try again.');
                }
            }
        });
    });
}); 
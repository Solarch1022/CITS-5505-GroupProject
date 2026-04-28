function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    }[character]));
}

function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

function readCurrentUserId(root) {
    const rootId = root?.dataset.currentUserId;
    const bodyId = document.body.dataset.currentUserId;
    return Number(rootId || bodyId || 0);
}

function attachSellImagePicker() {
    const form = document.querySelector('[data-sell-form]');
    const input = document.getElementById('itemImages');
    const previewRoot = document.getElementById('imagePreviewGrid');
    const notice = document.getElementById('sellImageNotice');

    if (!form || !input || !previewRoot) {
        return;
    }

    let selectedFiles = [];
    const maxImages = Number(form.dataset.maxImages || '6');

    const showNotice = (message) => {
        if (!notice) {
            return;
        }
        notice.textContent = message;
    };

    const getFileKey = (file) => [file.name, file.size, file.lastModified].join(':');

    const updateInputFiles = () => {
        const dataTransfer = new DataTransfer();
        selectedFiles.forEach((file) => {
            dataTransfer.items.add(file);
        });
        input.files = dataTransfer.files;
    };

    const renderPreviews = () => {
        previewRoot.innerHTML = '';

        if (!selectedFiles.length) {
            previewRoot.innerHTML = '<div class="empty-state compact">No images selected yet.</div>';
            updateInputFiles();
            return;
        }

        selectedFiles.forEach((file, index) => {
            const card = document.createElement('div');
            card.className = 'image-preview-card';

            const image = document.createElement('img');
            image.className = 'image-preview-thumb';
            image.alt = file.name;

            const meta = document.createElement('div');
            meta.className = 'image-preview-meta';

            if (index === 0) {
                const badge = document.createElement('span');
                badge.className = 'image-preview-badge';
                badge.textContent = 'Cover';
                meta.appendChild(badge);
            } else {
                const setCoverButton = document.createElement('button');
                setCoverButton.type = 'button';
                setCoverButton.className = 'image-preview-set-cover';
                setCoverButton.textContent = 'Set cover';
                setCoverButton.addEventListener('click', () => {
                    const [selectedImage] = selectedFiles.splice(index, 1);
                    selectedFiles.unshift(selectedImage);
                    renderPreviews();
                });
                meta.appendChild(setCoverButton);
            }

            const actions = document.createElement('div');
            actions.className = 'image-preview-actions';

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.className = 'image-preview-remove';
            removeButton.textContent = 'Remove';
            removeButton.addEventListener('click', () => {
                selectedFiles.splice(index, 1);
                renderPreviews();
            });
            actions.appendChild(removeButton);
            meta.appendChild(actions);

            const caption = document.createElement('span');
            caption.className = 'image-preview-name';
            caption.textContent = file.name;

            card.appendChild(image);
            card.appendChild(meta);
            card.appendChild(caption);
            previewRoot.appendChild(card);

            const reader = new FileReader();
            reader.onload = (event) => {
                image.src = event.target?.result || '';
            };
            reader.readAsDataURL(file);
        });

        updateInputFiles();
    };

    input.addEventListener('change', (event) => {
        const newFiles = Array.from(event.target.files || []);
        const existingKeys = new Set(selectedFiles.map((file) => getFileKey(file)));
        let skipped = 0;

        newFiles.forEach((file) => {
            const key = getFileKey(file);
            if (existingKeys.has(key) || selectedFiles.length >= maxImages) {
                skipped += 1;
                return;
            }

            existingKeys.add(key);
            selectedFiles.push(file);
        });

        showNotice(skipped ? `Some images were skipped. You can keep up to ${maxImages} unique images.` : '');
        renderPreviews();
        event.target.value = '';
    });

    form.addEventListener('submit', () => {
        updateInputFiles();
    });

    renderPreviews();
}

function attachItemGallery() {
    const gallery = document.querySelector('[data-gallery]');
    if (!gallery) {
        return;
    }

    const mainImage = gallery.querySelector('[data-gallery-main]');
    const counter = gallery.querySelector('[data-gallery-counter]');
    const thumbs = Array.from(gallery.querySelectorAll('[data-gallery-index]'));
    const stepButtons = Array.from(gallery.querySelectorAll('[data-gallery-step]'));

    if (!mainImage || !thumbs.length) {
        return;
    }

    let currentIndex = thumbs.findIndex((thumb) => thumb.classList.contains('active'));
    currentIndex = currentIndex >= 0 ? currentIndex : 0;

    const updateGallery = () => {
        const activeThumb = thumbs[currentIndex];
        const activeUrl = activeThumb.dataset.galleryUrl;

        mainImage.src = activeUrl;
        thumbs.forEach((thumb, index) => {
            thumb.classList.toggle('active', index === currentIndex);
        });

        if (counter) {
            counter.textContent = `${currentIndex + 1} / ${thumbs.length}`;
        }
    };

    thumbs.forEach((thumb) => {
        thumb.addEventListener('click', () => {
            currentIndex = Number(thumb.dataset.galleryIndex || 0);
            updateGallery();
        });
    });

    stepButtons.forEach((button) => {
        button.addEventListener('click', () => {
            const step = Number(button.dataset.galleryStep || 0);
            currentIndex = (currentIndex + step + thumbs.length) % thumbs.length;
            updateGallery();
        });
    });

    updateGallery();
}

function createMessageMarkup(message, currentUserId) {
    const mineClass = Number(message.sender.id) === currentUserId ? 'mine' : 'theirs';
    const author = escapeHtml(message.sender.full_name || message.sender.username);
    const body = escapeHtml(message.body).replace(/\n/g, '<br>');

    return `
        <div class="message-bubble ${mineClass}">
            <span class="message-author">${author}</span>
            <span class="message-body">${body}</span>
            <span class="message-time">${escapeHtml(message.created_at_display)}</span>
        </div>
    `;
}

function attachChatWidgets() {
    const chatRoots = document.querySelectorAll('[data-chat-root]');
    if (!chatRoots.length) {
        return;
    }

    chatRoots.forEach((root) => {
        const form = root.querySelector('[data-chat-form]');
        const thread = root.querySelector('[data-chat-thread]');
        const errorBox = root.querySelector('[data-chat-error]');
        const currentUserId = readCurrentUserId(root);
        let conversationId = Number(root.dataset.conversationId || 0);
        const itemId = Number(root.dataset.itemId || 0);
        let poller = null;

        const setError = (message) => {
            if (!errorBox) {
                return;
            }
            errorBox.textContent = message || '';
        };

        const renderConversation = (conversation) => {
            if (!thread) {
                return;
            }

            const messages = conversation.messages || [];
            thread.innerHTML = messages.length
                ? messages.map((message) => createMessageMarkup(message, currentUserId)).join('')
                : '<div class="empty-state compact">No messages yet.</div>';

            thread.scrollTop = thread.scrollHeight;
        };

        const fetchJson = async (url, options = {}) => {
            const response = await fetch(url, {
                credentials: 'same-origin',
                headers: {
                    Accept: 'application/json',
                    ...(options.headers || {}),
                },
                ...options,
            });
            const data = await response.json().catch(() => ({
                success: false,
                error: 'Unexpected response from server',
            }));
            data.httpStatus = response.status;
            return data;
        };

        const refreshConversation = async () => {
            if (!conversationId) {
                return;
            }

            const data = await fetchJson(`/api/conversations/${conversationId}`);
            if (data.success) {
                renderConversation(data.conversation);
            }
        };

        if (conversationId) {
            poller = window.setInterval(refreshConversation, 5000);
            window.addEventListener('beforeunload', () => {
                if (poller) {
                    window.clearInterval(poller);
                }
            }, { once: true });
        }

        if (!form) {
            return;
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            setError('');

            const textarea = form.querySelector('textarea[name="message"]');
            const message = textarea?.value.trim() || '';
            if (!message) {
                setError('Message cannot be empty.');
                return;
            }

            const endpoint = conversationId
                ? `/api/conversations/${conversationId}/messages`
                : `/api/items/${itemId}/conversations`;

            const data = await fetchJson(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken(),
                },
                body: JSON.stringify({ message }),
            });

            if (!data.success) {
                if (data.httpStatus === 401) {
                    window.location.href = '/login';
                    return;
                }
                setError(data.error || 'Message could not be sent.');
                return;
            }

            const conversation = data.conversation;
            conversationId = conversation.id;
            root.dataset.conversationId = String(conversationId);

            if (form.action.includes('/item/')) {
                form.action = `/conversations/${conversationId}/reply`;
            }

            renderConversation(conversation);
            textarea.value = '';

            if (!poller) {
                poller = window.setInterval(refreshConversation, 5000);
            }
        });
    });
}

function attachUnlistModal() {
    const backdrop = document.getElementById('unlistModalBackdrop');
    const form = document.getElementById('unlistDecisionForm');
    const text = document.getElementById('unlistModalText');
    const launchButtons = document.querySelectorAll('[data-unlist-launch]');
    const closeButtons = document.querySelectorAll('[data-modal-close]');

    if (!backdrop || !form || !text || !launchButtons.length) {
        return;
    }

    const closeModal = () => {
        backdrop.classList.add('hidden');
    };

    launchButtons.forEach((button) => {
        button.addEventListener('click', () => {
            const title = button.dataset.itemTitle || 'this listing';
            const actionUrl = button.dataset.actionUrl || '';
            form.action = actionUrl;
            text.textContent = `Choose whether to move "${title}" into the draft box or delete it permanently.`;
            backdrop.classList.remove('hidden');
        });
    });

    closeButtons.forEach((button) => {
        button.addEventListener('click', closeModal);
    });

    backdrop.addEventListener('click', (event) => {
        if (event.target === backdrop) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !backdrop.classList.contains('hidden')) {
            closeModal();
        }
    });
}

function attachWalletModal() {
    const backdrop = document.getElementById('walletModalBackdrop');
    const launchButtons = Array.from(document.querySelectorAll('[data-wallet-launch]'));
    const closeButtons = Array.from(document.querySelectorAll('[data-wallet-close]'));

    if (!backdrop || !launchButtons.length) {
        return;
    }

    const currentUrlWithoutHash = () => `${window.location.pathname}${window.location.search}`;

    const openModal = (syncHash = true) => {
        backdrop.classList.remove('hidden');
        document.body.classList.add('modal-open');
        if (syncHash && window.location.hash !== '#wallet') {
            history.replaceState(null, '', `${currentUrlWithoutHash()}#wallet`);
        }
    };

    const closeModal = (syncHash = true) => {
        backdrop.classList.add('hidden');
        document.body.classList.remove('modal-open');
        if (syncHash && window.location.hash === '#wallet') {
            history.replaceState(null, '', currentUrlWithoutHash());
        }
    };

    const syncWithHash = () => {
        if (window.location.hash === '#wallet') {
            openModal(false);
        } else {
            closeModal(false);
        }
    };

    launchButtons.forEach((button) => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            openModal(true);
        });
    });

    closeButtons.forEach((button) => {
        button.addEventListener('click', () => {
            closeModal(true);
        });
    });

    backdrop.addEventListener('click', (event) => {
        if (event.target === backdrop) {
            closeModal(true);
        }
    });

    window.addEventListener('hashchange', syncWithHash);
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !backdrop.classList.contains('hidden')) {
            closeModal(true);
        }
    });

    syncWithHash();
}

function attachWalletVisibilityToggle() {
    const toggleButtons = Array.from(document.querySelectorAll('[data-wallet-toggle]'));
    const sensitiveValues = Array.from(document.querySelectorAll('[data-wallet-sensitive]'));

    if (!toggleButtons.length || !sensitiveValues.length) {
        return;
    }

    let isVisible = window.localStorage.getItem('walletSensitiveVisible') === 'true';

    const renderState = () => {
        sensitiveValues.forEach((node) => {
            node.textContent = isVisible ? (node.dataset.value || '') : '****';
        });

        toggleButtons.forEach((button) => {
            button.textContent = isVisible ? 'Hide balances' : 'Reveal balances';
            button.setAttribute('aria-pressed', isVisible ? 'true' : 'false');
        });
    };

    toggleButtons.forEach((button) => {
        button.addEventListener('click', () => {
            isVisible = !isVisible;
            window.localStorage.setItem('walletSensitiveVisible', isVisible ? 'true' : 'false');
            renderState();
        });
    });

    renderState();
}

function attachUserDropdown() {
    const userMenuBtn = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (!userMenuBtn || !userDropdown) {
        return;
    }

    userMenuBtn.addEventListener('click', () => {
        userDropdown.classList.toggle('active');
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.nav-user-dropdown')) {
            userDropdown.classList.remove('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    attachSellImagePicker();
    attachItemGallery();
    attachChatWidgets();
    attachUnlistModal();
    attachWalletModal();
    attachWalletVisibilityToggle();
    attachUserDropdown();
});

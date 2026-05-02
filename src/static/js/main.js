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
    const author = escapeHtml(message.sender.username);
    const body = escapeHtml(message.body).replace(/\n/g, '<br>');
    const avatarMarkup = message.sender.avatar_url
        ? `<img src="${escapeHtml(message.sender.avatar_url)}" alt="${author} avatar" class="chat-avatar">`
        : `<span class="chat-avatar chat-avatar-fallback">${escapeHtml((message.sender.username || '?').charAt(0).toUpperCase())}</span>`;

    return `
        <div class="message-row ${mineClass}">
            ${avatarMarkup}
            <div class="message-bubble ${mineClass}">
                <span class="message-author">${author}</span>
                <span class="message-body">${body}</span>
                <span class="message-time">${escapeHtml(message.created_at_display)}</span>
            </div>
        </div>
    `;
}

function attachChatWidgets() {
    const chatRoots = document.querySelectorAll('[data-chat-root]');
    if (!chatRoots.length) {
        return;
    }

    chatRoots.forEach((root) => {
        if (root.closest('[data-inbox-root]')) {
            return;
        }

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

function attachReferralCopyButton() {
    const copyButton = document.querySelector('[data-copy-referral]');
    const referralCodeText = document.getElementById('referralCodeText');
    const feedback = document.getElementById('copyFeedback');

    if (!copyButton || !referralCodeText || !feedback) {
        return;
    }

    copyButton.addEventListener('click', async () => {
        const code = referralCodeText.textContent.trim();

        if (!code) {
            return;
        }

        try {
            await navigator.clipboard.writeText(code);

            feedback.style.display = 'inline';

            setTimeout(() => {
                feedback.style.display = 'none';
            }, 1500);
        } catch (error) {
            feedback.textContent = 'Copy failed';
            feedback.style.display = 'inline';

            setTimeout(() => {
                feedback.textContent = 'Copied!';
                feedback.style.display = 'none';
            }, 1500);
        }
    });
}

function attachAvatarCropper() {
    const modal = document.querySelector('[data-avatar-modal]');
    const openButton = document.querySelector('[data-avatar-modal-open]');
    const closeButtons = Array.from(document.querySelectorAll('[data-avatar-modal-close]'));
    const form = document.querySelector('[data-avatar-crop-form]');
    const fileInput = document.querySelector('[data-avatar-file]');
    const canvas = document.querySelector('[data-avatar-canvas]');
    const emptyState = document.querySelector('[data-avatar-empty]');
    const zoomInput = document.querySelector('[data-avatar-zoom]');
    const avatarDataInput = document.querySelector('[data-avatar-data]');
    const saveButton = document.querySelector('[data-avatar-save]');

    if (!modal || !openButton || !form || !fileInput || !canvas || !zoomInput || !avatarDataInput || !saveButton) {
        return;
    }

    const ctx = canvas.getContext('2d');
    const cropSize = canvas.width;
    let image = null;
    let objectUrl = '';
    let minScale = 1;
    let scale = 1;
    let offsetX = 0;
    let offsetY = 0;
    let isDragging = false;
    let lastPointerX = 0;
    let lastPointerY = 0;

    const openModal = () => {
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');
    };

    const closeModal = () => {
        modal.classList.add('hidden');
        document.body.classList.remove('modal-open');
    };

    const clampOffset = () => {
        if (!image) {
            return;
        }

        const renderedWidth = image.width * scale;
        const renderedHeight = image.height * scale;

        if (renderedWidth <= cropSize) {
            offsetX = (cropSize - renderedWidth) / 2;
        } else {
            offsetX = Math.min(0, Math.max(cropSize - renderedWidth, offsetX));
        }

        if (renderedHeight <= cropSize) {
            offsetY = (cropSize - renderedHeight) / 2;
        } else {
            offsetY = Math.min(0, Math.max(cropSize - renderedHeight, offsetY));
        }
    };

    const drawCropPreview = () => {
        ctx.clearRect(0, 0, cropSize, cropSize);
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(0, 0, cropSize, cropSize);

        if (!image) {
            return;
        }

        clampOffset();
        ctx.drawImage(image, offsetX, offsetY, image.width * scale, image.height * scale);

        ctx.save();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.92)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(cropSize / 2, cropSize / 2, cropSize / 2 - 12, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
    };

    const loadImageFile = (file) => {
        if (!file) {
            return;
        }

        if (objectUrl) {
            URL.revokeObjectURL(objectUrl);
        }

        objectUrl = URL.createObjectURL(file);
        image = new Image();
        image.onload = () => {
            minScale = Math.max(cropSize / image.width, cropSize / image.height);
            scale = minScale;
            offsetX = (cropSize - image.width * scale) / 2;
            offsetY = (cropSize - image.height * scale) / 2;
            zoomInput.value = '1';
            zoomInput.disabled = false;
            saveButton.disabled = false;
            if (emptyState) {
                emptyState.classList.add('hidden');
            }
            drawCropPreview();
        };
        image.src = objectUrl;
    };

    openButton.addEventListener('click', openModal);

    closeButtons.forEach((button) => {
        button.addEventListener('click', closeModal);
    });

    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
            closeModal();
        }
    });

    fileInput.addEventListener('change', (event) => {
        const [file] = Array.from(event.target.files || []);
        loadImageFile(file);
    });

    zoomInput.addEventListener('input', () => {
        if (!image) {
            return;
        }

        const oldScale = scale;
        const centerImageX = (cropSize / 2 - offsetX) / oldScale;
        const centerImageY = (cropSize / 2 - offsetY) / oldScale;
        scale = minScale * Number(zoomInput.value || 1);
        offsetX = cropSize / 2 - centerImageX * scale;
        offsetY = cropSize / 2 - centerImageY * scale;
        drawCropPreview();
    });

    canvas.addEventListener('pointerdown', (event) => {
        if (!image) {
            return;
        }

        isDragging = true;
        lastPointerX = event.clientX;
        lastPointerY = event.clientY;
        canvas.classList.add('dragging');
        canvas.setPointerCapture(event.pointerId);
    });

    canvas.addEventListener('pointermove', (event) => {
        if (!isDragging || !image) {
            return;
        }

        offsetX += event.clientX - lastPointerX;
        offsetY += event.clientY - lastPointerY;
        lastPointerX = event.clientX;
        lastPointerY = event.clientY;
        drawCropPreview();
    });

    const stopDragging = (event) => {
        if (!isDragging) {
            return;
        }

        isDragging = false;
        canvas.classList.remove('dragging');
        if (event.pointerId !== undefined) {
            canvas.releasePointerCapture(event.pointerId);
        }
    };

    canvas.addEventListener('pointerup', stopDragging);
    canvas.addEventListener('pointercancel', stopDragging);
    canvas.addEventListener('pointerleave', stopDragging);

    form.addEventListener('submit', (event) => {
        if (!image) {
            event.preventDefault();
            return;
        }

        drawCropPreview();
        avatarDataInput.value = canvas.toDataURL('image/png');
    });
}

function createConversationCardMarkup(conversation, activeConversationId) {
    const latestMessage = conversation.latest_message || null;
    const latestMessageId = latestMessage?.id || '';
    const latestSenderId = latestMessage?.sender?.id || '';
    const activeClass = Number(conversation.id) === activeConversationId ? ' active' : '';
    const countLabel = `${conversation.message_count} msg`;
    const counterpartInitial = (conversation.counterpart.username || '?').charAt(0).toUpperCase();
    const avatarMarkup = conversation.counterpart.avatar_url
        ? `<img src="${escapeHtml(conversation.counterpart.avatar_url)}" alt="${escapeHtml(conversation.counterpart.username)} avatar" class="conversation-avatar">`
        : `<span class="conversation-avatar conversation-avatar-fallback">${escapeHtml(counterpartInitial)}</span>`;

    return `
        <a
            href="/dashboard?conversation=${encodeURIComponent(conversation.id)}#inbox"
            class="conversation-item${activeClass}"
            data-conversation-card
            data-conversation-id="${escapeHtml(conversation.id)}"
            data-latest-message-id="${escapeHtml(latestMessageId)}"
            data-latest-sender-id="${escapeHtml(latestSenderId)}"
            data-message-count="${escapeHtml(conversation.message_count)}"
        >
            <div class="conversation-copy">
                ${avatarMarkup}
                <div>
                    <strong>${escapeHtml(conversation.item.title)}</strong>
                    <p>${escapeHtml(conversation.counterpart.username)}</p>
                </div>
            </div>
            <div class="conversation-meta">
                <span data-conversation-count>${escapeHtml(countLabel)}</span>
                <span class="conversation-alert hidden" data-conversation-alert>New</span>
            </div>
        </a>
    `;
}

function createInboxEmptyPanelMarkup() {
    return `
        <div class="inbox-empty-panel" aria-hidden="true">
            <span>Latest news</span>
        </div>
    `;
}

function createConversationPanelMarkup(conversation, currentUserId) {
    const messages = conversation.messages || [];
    const statusLabel = conversation.item.is_sold ? 'Listing sold' : 'Listing active';
    const counterpartInitial = (conversation.counterpart.username || '?').charAt(0).toUpperCase();
    const avatarMarkup = conversation.counterpart.avatar_url
        ? `<img src="${escapeHtml(conversation.counterpart.avatar_url)}" alt="${escapeHtml(conversation.counterpart.username)} avatar" class="chat-header-avatar">`
        : `<span class="chat-header-avatar chat-avatar-fallback">${escapeHtml(counterpartInitial)}</span>`;

    return `
        <div class="chat-header">
            <div class="chat-title-row">
                ${avatarMarkup}
                <div>
                    <h3>${escapeHtml(conversation.item.title)}</h3>
                    <p class="panel-text">Conversation with ${escapeHtml(conversation.counterpart.username)}</p>
                </div>
            </div>
            <div class="chat-status">${escapeHtml(statusLabel)}</div>
        </div>
        <div class="message-thread" data-chat-thread>
            ${messages.length
                ? messages.map((message) => createMessageMarkup(message, currentUserId)).join('')
                : '<div class="empty-state compact">No messages yet.</div>'}
        </div>
        <form method="post" action="/conversations/${encodeURIComponent(conversation.id)}/reply" class="chat-form" data-chat-form>
            <input type="hidden" name="csrf_token" value="${escapeHtml(getCsrfToken())}">
            <input type="hidden" name="next" value="/dashboard?conversation=${escapeHtml(conversation.id)}#inbox">
            <textarea name="message" rows="3" placeholder="Reply to this conversation..." required></textarea>
            <div class="chat-feedback" data-chat-error></div>
            <button type="submit" class="btn btn-primary">Send reply</button>
        </form>
    `;
}

function attachInboxNotifications() {
    const root = document.querySelector('[data-inbox-root]');
    if (!root) {
        return;
    }

    const list = root.querySelector('[data-conversation-list]');
    const chatRoot = root.querySelector('[data-chat-root]');
    if (!list || !chatRoot) {
        return;
    }

    const currentUserId = readCurrentUserId(root);
    let activeConversationId = Number(root.dataset.activeConversationId || 0);
    let activeConversationPoller = null;

    const readMarkerKey = (conversationId) => `uwa-secondhand:inbox:${currentUserId}:${conversationId}:latest-read`;

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

    const getReadMarker = (conversationId) => {
        try {
            return Number(window.localStorage.getItem(readMarkerKey(conversationId)) || 0);
        } catch (error) {
            return 0;
        }
    };

    const setReadMarker = (conversationId, latestMessageId) => {
        if (!conversationId || !latestMessageId) {
            return;
        }

        try {
            window.localStorage.setItem(readMarkerKey(conversationId), String(latestMessageId));
        } catch (error) {
            // Ignore storage failures; the inbox still works without persisted read state.
        }
    };

    const markActiveConversationRead = () => {
        if (!activeConversationId) {
            return;
        }

        const activeCard = list.querySelector(`[data-conversation-card][data-conversation-id="${activeConversationId}"]`);
        const latestMessageId = Number(activeCard?.dataset.latestMessageId || 0);
        setReadMarker(activeConversationId, latestMessageId);
    };

    const updateUnreadBadges = () => {
        list.querySelectorAll('[data-conversation-card]').forEach((card) => {
            const conversationId = Number(card.dataset.conversationId || 0);
            const latestMessageId = Number(card.dataset.latestMessageId || 0);
            const latestSenderId = Number(card.dataset.latestSenderId || 0);
            const readMarker = getReadMarker(conversationId);
            const hasUnread = Boolean(
                latestMessageId
                && latestSenderId
                && latestSenderId !== currentUserId
                && latestMessageId > readMarker
            );
            const alert = card.querySelector('[data-conversation-alert]');

            card.classList.toggle('has-new-message', hasUnread);
            if (alert) {
                alert.classList.toggle('hidden', !hasUnread);
            }
        });
    };

    const updateConversationCardFromConversation = (conversation) => {
        const card = list.querySelector(`[data-conversation-card][data-conversation-id="${conversation.id}"]`);
        if (!card) {
            return;
        }

        const latestMessage = conversation.latest_message || null;
        card.dataset.latestMessageId = latestMessage?.id || '';
        card.dataset.latestSenderId = latestMessage?.sender?.id || '';
        card.dataset.messageCount = String(conversation.message_count || 0);

        const count = card.querySelector('[data-conversation-count]');
        if (count) {
            count.textContent = `${conversation.message_count || 0} msg`;
        }
    };

    const renderConversationPanel = (conversation) => {
        activeConversationId = Number(conversation.id);
        root.dataset.activeConversationId = String(activeConversationId);
        chatRoot.dataset.conversationId = String(activeConversationId);
        chatRoot.innerHTML = createConversationPanelMarkup(conversation, currentUserId);

        const thread = chatRoot.querySelector('[data-chat-thread]');
        if (thread) {
            thread.scrollTop = thread.scrollHeight;
        }
    };

    const updateActiveConversationThread = (conversation) => {
        const thread = chatRoot.querySelector('[data-chat-thread]');
        if (!thread) {
            renderConversationPanel(conversation);
            return;
        }

        const messages = conversation.messages || [];
        thread.innerHTML = messages.length
            ? messages.map((message) => createMessageMarkup(message, currentUserId)).join('')
            : '<div class="empty-state compact">No messages yet.</div>';
        thread.scrollTop = thread.scrollHeight;
    };

    const updateActiveCard = () => {
        list.querySelectorAll('[data-conversation-card]').forEach((card) => {
            const conversationId = Number(card.dataset.conversationId || 0);
            card.classList.toggle('active', Boolean(activeConversationId && conversationId === activeConversationId));
        });
    };

    const refreshActiveConversation = async () => {
        if (!activeConversationId) {
            return;
        }

        const data = await fetchJson(`/api/conversations/${activeConversationId}`);
        if (data.success) {
            updateActiveConversationThread(data.conversation);
            updateConversationCardFromConversation(data.conversation);
            updateUnreadBadges();
        }
    };

    const restartActiveConversationPolling = () => {
        if (activeConversationPoller) {
            window.clearInterval(activeConversationPoller);
            activeConversationPoller = null;
        }

        if (activeConversationId) {
            activeConversationPoller = window.setInterval(refreshActiveConversation, 5000);
        }
    };

    const openConversation = async (conversationId, { updateUrl = true } = {}) => {
        if (!conversationId) {
            return;
        }

        chatRoot.innerHTML = '<div class="empty-state compact">Loading conversation...</div>';

        const data = await fetchJson(`/api/conversations/${conversationId}`);
        if (!data.success) {
            chatRoot.innerHTML = `<div class="empty-state compact">${escapeHtml(data.error || 'Conversation could not be loaded.')}</div>`;
            return;
        }

        renderConversationPanel(data.conversation);
        markActiveConversationRead();
        updateActiveCard();
        updateUnreadBadges();
        restartActiveConversationPolling();

        if (updateUrl) {
            const nextUrl = `/dashboard?conversation=${encodeURIComponent(activeConversationId)}#inbox`;
            window.history.pushState({ conversationId: activeConversationId }, '', nextUrl);
        }
    };

    const renderConversationList = (conversations) => {
        if (!conversations.length) {
            list.innerHTML = '<div class="empty-state compact">No conversations yet. Message a seller from any listing.</div>';
            chatRoot.innerHTML = createInboxEmptyPanelMarkup();
            return;
        }

        list.innerHTML = conversations
            .map((conversation) => createConversationCardMarkup(conversation, activeConversationId))
            .join('');

        updateActiveCard();
        updateUnreadBadges();
    };

    const refreshConversations = async () => {
        try {
            const response = await fetch('/api/conversations', {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
            });
            const data = await response.json();

            if (data.success) {
                renderConversationList(data.conversations || []);
            }
        } catch (error) {
            // Keep the current server-rendered list if a refresh fails.
        }
    };

    list.addEventListener('click', (event) => {
        const card = event.target.closest('[data-conversation-card]');
        if (!card) {
            return;
        }

        event.preventDefault();

        const conversationId = Number(card.dataset.conversationId || 0);
        setReadMarker(conversationId, Number(card.dataset.latestMessageId || 0));
        openConversation(conversationId);
    });

    chatRoot.addEventListener('submit', async (event) => {
        const form = event.target.closest('[data-chat-form]');
        if (!form) {
            return;
        }

        event.preventDefault();

        const errorBox = form.querySelector('[data-chat-error]');
        const textarea = form.querySelector('textarea[name="message"]');
        const message = textarea?.value.trim() || '';

        if (errorBox) {
            errorBox.textContent = '';
        }

        if (!message) {
            if (errorBox) {
                errorBox.textContent = 'Message cannot be empty.';
            }
            return;
        }

        const data = await fetchJson(`/api/conversations/${activeConversationId}/messages`, {
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

            if (errorBox) {
                errorBox.textContent = data.error || 'Message could not be sent.';
            }
            return;
        }

        textarea.value = '';
        renderConversationPanel(data.conversation);
        markActiveConversationRead();
        updateUnreadBadges();
        refreshConversations();
    });

    window.addEventListener('popstate', () => {
        const params = new URLSearchParams(window.location.search);
        const conversationId = Number(params.get('conversation') || 0);

        if (conversationId) {
            openConversation(conversationId, { updateUrl: false });
            return;
        }

        activeConversationId = 0;
        root.dataset.activeConversationId = '';
        chatRoot.dataset.conversationId = '';
        chatRoot.innerHTML = createInboxEmptyPanelMarkup();
        updateActiveCard();
        updateUnreadBadges();
        restartActiveConversationPolling();
    });

    markActiveConversationRead();
    updateActiveCard();
    updateUnreadBadges();
    restartActiveConversationPolling();

    const poller = window.setInterval(refreshConversations, 5000);
    window.addEventListener('beforeunload', () => {
        window.clearInterval(poller);
        if (activeConversationPoller) {
            window.clearInterval(activeConversationPoller);
        }
    }, { once: true });
}

document.addEventListener('DOMContentLoaded', () => {
    attachSellImagePicker();
    attachItemGallery();
    attachChatWidgets();
    attachInboxNotifications();
    attachAvatarCropper();
    attachUnlistModal();
    attachWalletModal();
    attachWalletVisibilityToggle();
    attachUserDropdown();
    attachReferralCopyButton();
});

CTFd._internal.challenge.data = undefined;
CTFd._internal.challenge.renderer = null;
CTFd._internal.challenge.preRender = function () {};
CTFd._internal.challenge.render = null;

CTFd._internal.challenge.postRender = function () {
    loadDehlizInfo();
};

if (window.$ === undefined) window.$ = CTFd.lib.$;

window.dehlizTimer = undefined;

function formatSeconds(secs) {
    if (secs < 0) return "00:00";
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    var mm = m < 10 ? "0" + m : m;
    var ss = s < 10 ? "0" + s : s;
    return mm + ":" + ss;
}

function loadDehlizInfo() {
    if (!CTFd._internal.challenge.data) return;
    var challenge_id = CTFd._internal.challenge.data.id;
    var url = "/plugins/ctfd-dehliz/container?challenge_id=" + challenge_id;

    CTFd.fetch(url, {
        method: "GET",
        credentials: "same-origin",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    }).then(function (res) {
        return res.json();
    }).then(function (res) {
        if (window.dehlizTimer) {
            clearInterval(window.dehlizTimer);
            window.dehlizTimer = undefined;
        }

        if (res.success && res.data && res.data.status === "running") {
            var data = res.data;
            $("#dehliz-countdown").text(formatSeconds(data.remaining_time));
            $("#dehliz-lan-domain").text(data.domain);
            $("#dehliz-user-access").html(data.user_access);

            $("#dehliz-panel-stopped").hide();
            $("#dehliz-panel-started").show();

            var currentSecs = data.remaining_time;
            window.dehlizTimer = setInterval(function () {
                currentSecs -= 1;
                if (currentSecs <= 0) {
                    clearInterval(window.dehlizTimer);
                    loadDehlizInfo();
                    return;
                }
                $("#dehliz-countdown").text(formatSeconds(currentSecs));
            }, 1000);
        } else {
            $("#dehliz-panel-started").hide();
            $("#dehliz-panel-stopped").show();
            $("#dehliz-btn-boot").text("🚀 Özel Soru Labını Başlat").prop("disabled", false);
        }
    }).catch(function (err) {
        console.error("[Dehliz] Durum kontrol hatası:", err);
    });
}

window.dehlizBoot = function () {
    if (!CTFd._internal.challenge.data) return;
    var challenge_id = CTFd._internal.challenge.data.id;
    var url = "/plugins/ctfd-dehliz/container";

    $("#dehliz-btn-boot").text("⏳ Başlatılıyor (Lütfen Bekleyin)...").prop("disabled", true);

    CTFd.fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(function (res) {
        return res.json();
    }).then(function (res) {
        if (res.success) {
            loadDehlizInfo();
        } else {
            alert("Hata: " + (res.message || "Konteyner başlatılamadı"));
            $("#dehliz-btn-boot").text("🚀 Özel Soru Labını Başlat").prop("disabled", false);
        }
    }).catch(function (err) {
        alert("Bağlantı hatası: " + err);
        $("#dehliz-btn-boot").text("🚀 Özel Soru Labını Başlat").prop("disabled", false);
    });
};

window.dehlizRenew = function () {
    if (!CTFd._internal.challenge.data) return;
    var challenge_id = CTFd._internal.challenge.data.id;
    var url = "/plugins/ctfd-dehliz/container/renew";

    $("#dehliz-btn-renew").text("⏳ Uzatılıyor...").prop("disabled", true);

    CTFd.fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(function (res) {
        return res.json();
    }).then(function (res) {
        $("#dehliz-btn-renew").text("🔄 Süreyi Uzat (+30 dk)").prop("disabled", false);
        if (res.success) {
            loadDehlizInfo();
        } else {
            alert("Uyarı: " + (res.message || "Süre uzatılamadı"));
        }
    }).catch(function (err) {
        $("#dehliz-btn-renew").text("🔄 Süreyi Uzat (+30 dk)").prop("disabled", false);
        alert("Bağlantı hatası: " + err);
    });
};

window.dehlizDestroy = function () {
    if (!confirm("Bu canlı lab konteynerini kapatmak istediğinize emin misiniz?")) return;
    if (!CTFd._internal.challenge.data) return;
    var challenge_id = CTFd._internal.challenge.data.id;
    var url = "/plugins/ctfd-dehliz/container";

    $("#dehliz-btn-destroy").text("⏳ Kapatılıyor...").prop("disabled", true);

    CTFd.fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(function (res) {
        return res.json();
    }).then(function (res) {
        $("#dehliz-btn-destroy").text("⏹️ Labı Kapat").prop("disabled", false);
        loadDehlizInfo();
    }).catch(function (err) {
        $("#dehliz-btn-destroy").text("⏹️ Labı Kapat").prop("disabled", false);
        alert("Bağlantı hatası: " + err);
    });
};

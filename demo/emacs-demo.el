;;; emacs-demo.el --- tuisla demo: org-present slides + tuisla in eat  -*- lexical-binding: t -*-
;; Run by demo/record-emacs.py as: emacs -Q -nw -l emacs-demo.el
;; Env: DEMO_ORG (slides), DEMO_TUISLA (tuisla to run).  Needs org-present, eat.

(require 'org-present)
(require 'eat)

(setq inhibit-startup-screen t
      ring-bell-function #'ignore
      eat-kill-buffer-on-exit t)
(menu-bar-mode -1)
(fset 'display-startup-echo-area-message #'ignore)
(setq-default mode-line-format nil)
(set-display-table-slot standard-display-table 'vertical-border ?│)

(defvar demo-org-win nil)
(defvar demo-eat-buf nil)

(defun demo-typed (text &optional gap)
  (mapcar (lambda (ch) (cons (or gap 0.12) (string ch))) text))

;; Each step: (DELAY-BEFORE . ACTION); ACTION is slide, quit, or keys to send.
;; Same timeline as demo/record-tmux.py.
(defvar demo-steps
  `((0   . slide)                       ; Dashboard
    (4.0 . slide) (0.8 . "u") (2.5 . "u")
    (1.5 . slide) (0.8 . "b")
    (2.5 . slide) (0.8 . "i") (2.5 . "i")
    (1.0 . slide) (0.8 . "h") (4.0 . "h")
    (0.5 . slide) (0.8 . "?") (2.0 . "j") (0.3 . "j") (0.3 . "j") (0.3 . "j")
    (1.5 . slide) (0.8 . "/") ,@(demo-typed "climate" 0.15)
    (0.8 . "\r") (2.0 . "n") (2.0 . "q")
    (0.5 . slide) (0.8 . ":") ,@(demo-typed "ch")
    (0.6 . "\t") (1.8 . "\t") ,@(demo-typed "limit 80") (1.2 . "\r")
    (3.0 . slide) (0.8 . "H")
    (3.0 . slide) (0.8 . "z") (3.5 . "q")
    (0.5 . slide) (0.8 . "+") (1.0 . "h") (3.5 . "h")
    (0.5 . slide) (0.8 . "m") (2.2 . "m") (2.2 . "m")
    (2.5 . end)))   ; the cast ends here, before anything quits, so a GIF loops

(defconst demo-end-marker "\e]0;tuisla-demo-end\a"
  "Window-title escape the recorder cuts the cast at.")

(defun demo-do (action)
  (cond
   ((eq action 'slide)
    (with-selected-window demo-org-win (org-present-next)))
   ((eq action 'end)
    (send-string-to-terminal demo-end-marker)
    (kill-emacs 0))
   (t (with-current-buffer demo-eat-buf
        (eat-term-send-string eat-terminal action)))))

(defun demo-run (steps)
  (when steps
    (run-at-time (car (car steps)) nil
                 (lambda ()
                   (demo-do (cdr (car steps)))
                   (demo-run (cdr steps))))))

(defun demo-start ()
  ;; Left: the slides.  Right: tuisla in eat.
  (find-file (getenv "DEMO_ORG"))
  (setq demo-org-win (selected-window))
  (setq header-line-format '(:propertize " Animation table of content: " face (:inverse-video t :weight bold)))
  (visual-line-mode 1)                  ; wrap long slide lines
  (org-present)
  ;; org-present starts just before the first heading; this lands on the
  ;; title slide, so the timeline's first `slide' shows the Dashboard.
  (org-present-next)
  (org-present-hide-cursor)
  (let ((right (split-window-right 56)))
    (select-window right)
    (eat (concat "python3 -B " (shell-quote-argument (getenv "DEMO_TUISLA")) " -m ro"))
    (setq demo-eat-buf (window-buffer right))
    (with-current-buffer demo-eat-buf
      (setq header-line-format
            '(:propertize " tuisla demo below: " face (:inverse-video t :weight bold)))))
  (message nil)
  ;; Title slide for 3 s, then the timeline.
  (run-at-time 3 nil #'demo-run demo-steps))

(add-hook 'emacs-startup-hook #'demo-start)

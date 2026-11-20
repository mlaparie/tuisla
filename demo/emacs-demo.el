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
    (4.0 . slide) (0.8 . "h")                        ; help stays open for the next 5
    (2.0 . slide) (0.8 . "+") (1.5 . "+") (1.5 . "-") (1.5 . "-")
    ;; Toggle in help, close help to see it on the dashboard, revert it there
    ;; (colors stay on), reopen help.  Style ends on the dashboard.
    (1.5 . slide) (0.8 . "b") (1.2 . "h") (2.5 . "h")
    (1.0 . slide) (0.8 . "i") (1.2 . "h") (2.5 . "i") (1.5 . "h")
    (1.0 . slide) (0.8 . "u") (1.2 . "h") (2.5 . "u") (1.5 . "h")
    (1.0 . slide) (0.8 . "s") (1.2 . "h") (2.5 . "s")
    (2.5 . slide) (0.8 . "?") (2.0 . "j") (0.3 . "j") (0.3 . "j") (0.3 . "j")
    (1.5 . slide) (0.8 . "/") ,@(demo-typed "climate" 0.15)
    (0.8 . "\r") (2.0 . "n") (2.0 . "q")
    (0.5 . slide) (0.8 . ":") ,@(demo-typed "ch")
    (0.6 . "\t") (1.8 . "\t") ,@(demo-typed "limit 80") (1.2 . "\r")
    (2.5 . ":") ,@(demo-typed "temp 22") (1.0 . "\r")
    (3.0 . slide) (0.8 . "H")
    (3.0 . slide) (0.8 . "z") (3.5 . "q")
    (0.5 . slide) (0.8 . "m") (2.2 . "m") (2.2 . "m")
    (2.5 . end)))   ; the cast ends here, before anything quits, so a GIF loops

(defconst demo-end-marker "\e]0;tuisla-demo-end\a"
  "Window-title escape the recorder cuts the cast at.")

(defvar demo-keys nil "Keys pressed so far, newest first.")

(defun demo-show-key (key)
  "Show the last keys pressed in the echo area, newest highlighted."
  (push (pcase key ("\r" "⏎") ("\t" "Tab") (" " "␣") (_ key)) demo-keys)
  (let ((recent (reverse (seq-take demo-keys 20))))
    (message "%s %s%s"
             (propertize "Keys pressed:" 'face 'shadow)
             (mapconcat (lambda (k) (format " %s " k)) (butlast recent) "")
             (propertize (format " %s " (car (last recent)))
                         'face '(:inverse-video t :weight bold)))))

(defun demo-do (action)
  (cond
   ((eq action 'slide)
    (with-selected-window demo-org-win (org-present-next)))
   ((eq action 'end)
    (send-string-to-terminal demo-end-marker)
    (kill-emacs 0))
   (t (with-current-buffer demo-eat-buf
        (eat-term-send-string eat-terminal action))
      (demo-show-key action))))

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

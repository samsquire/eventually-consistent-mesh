(ns jepsen.etcdemo
  (:require [clojure.tools.logging :refer :all]
            [clojure.string :as str]
            [jepsen [cli :as cli]
                    [control :as c]
                    [db :as db]
                    [tests :as tests]
                    [client :as client]
                    [generator :as gen]
                    [tests :as tests]
                    ]
            [jepsen.control.util :as cu]
            [jepsen.os.debian :as debian]))

(def dir     "/tmp/ecm")
(def binary "/usr/bin/python3")
(def logfile (str dir "/ecm.log"))
(def pidfile (str dir "/ecm.pid"))

(defn db
  "eventually-consistent-mesh DB for a particular version."
  [version]
  (reify db/DB
    (setup! [_ test node]
      (info node "installing eventually-consistent-mesh" version)

      (c/exec ["sudo", "rm", "-rf", "/tmp/ecm"])
      (c/exec ["mkdir", "-p", "/tmp/ecm"])
      (c/upload "../node_cluster.py" "/tmp/ecm")
      (c/upload "nodes" "/tmp/ecm")
       (c/su 
       (cu/start-daemon!
          {:logfile logfile
           :pidfile pidfile
           :chdir   dir
           :background false}
       binary
       "/tmp/ecm/node_cluster.py"
       :run
       :--index
       node
       :--nodes-file
       "/tmp/ecm/nodes"))
       (Thread/sleep 5000))
    

    (teardown! [_ test node]
      (info node "tearing down eventually-consistent-mesh")
       (cu/stop-daemon! binary pidfile)
       (c/su 
        (c/exec ["pkill", "-f", "python3"])))

    db/LogFiles
        (log-files [_ test node]
          [logfile])))


(defrecord Client [conn]
  client/Client
  (open! [this test node]
    this)

  (setup! [this test])

  (invoke! [_ test op])

  (teardown! [this test])

  (close! [_ test]))

(defn etcd-test
  "Given an options map from the command line runner (e.g. :nodes, :ssh,
  :concurrency, ...), constructs a test map."
  [opts]
  (merge tests/noop-test
         {:pure-generators true}
         opts
         {
          :db (db "1")
          :client (Client. nil)
         }))

(defn -main
  "Handles command line arguments. Can either run a test, or a web server for
  browsing results."
  [& args]
  (cli/run! (cli/single-test-cmd {:test-fn etcd-test})
            args))


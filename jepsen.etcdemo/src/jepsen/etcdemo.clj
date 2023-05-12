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
(import (java.net Socket))
(import (java.io DataInputStream DataOutputStream))
(import (java.io BufferedInputStream BufferedInputStream))
(import (java.io BufferedOutputStream BufferedOutputStream))
(import (java.nio ByteBuffer ByteBuffer))
(import (java.nio ByteOrder ByteOrder))
(require '[clojure.string :as str])
(require '[clojure.pprint])

(def dir     "/tmp/ecm")
(def binary "/usr/bin/python3")
(def logfile (str dir "/ecm.log"))
(def pidfile (str dir "/ecm.pid"))

(defn r   [_ _] {:type :invoke, :f :read, :value nil})
(defn w   [_ _] {:type :invoke, :f :write, :value (rand-int 5)})
(defn cas [_ _] {:type :invoke, :f :cas, :value [(rand-int 5) (rand-int 5)]})

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
           :chdir   dir
           :background? true}
       binary  
       :node_cluster.py
       :run
       :--index
       node
       :--nodes-file
       :nodes))
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
  (let [node_data (slurp "nodes") 
     lines (str/split node_data #"\n") 
     index (loop [i 0]
      (let [inext (+ i 1)]
        (if (= (nth lines i) node)
           i
          (if (< i (count lines))
            (recur inext)
            -1)
            ))) ]
        (def port (+ 65432 index))
        (def command "server clientonly\t")
        (def IPaddress node)
        (let [size (ByteBuffer/allocate Long/BYTES) ]
          (loop [] 
            (when (try
            
              (.println *err* (str "Connecting to server " node " on port " port))
              (comment (.order size ByteOrder/LITTLE_ENDIAN))
              (.rewind size) 
              (def socket (Socket. IPaddress port))
              (comment (.println *err* (str (.isConnected socket))))
              (def in (BufferedInputStream. (.getInputStream socket)))
              (def out (BufferedOutputStream. (.getOutputStream socket)))
              (.println *err* (str size))
              (.putLong size 0 (count command))
               
              (.println *err* (str "size of array is " (count (.array size))))
              (.write out (.array size) 0 8)
              (.write out (.getBytes command) 0 (count (.getBytes command)))
              (.flush out)
              (comment (def response (.readUTF in)))
              (println "Output: " command)
             (assoc this :in in)
             (assoc this :socket socket)
             (assoc this :out out)
             false 
         (catch Exception e
          (.println *err* (str e))
          true 
         )
          )
         (recur)
          )))
      ) this)

  (setup! [this test])

  (invoke! [this test op]
      (case (:f op)
        :read (assoc op :type :ok, :value 0
        

    )))

  (teardown! [this test])

  (close! [this test]
  (.close (this :socket))  
  )
)
(defn ecm-test
  "Given an options map from the command line runner (e.g. :nodes, :ssh,
  :concurrency, ...), constructs a test map."
  [opts]
  (merge tests/noop-test
         opts
         {:pure-generators true
          :db (db "1")
          :client (Client. nil)
          :generator       (->> [r w]
                                (gen/stagger 1)
                                (gen/nemesis nil)
                                (gen/time-limit 15))
         }
         ))

(defn -main
  "Handles command line arguments. Can either run a test, or a web server for
  browsing results."
  [& args]
  (cli/run! (cli/single-test-cmd {:test-fn ecm-test})
            args))

